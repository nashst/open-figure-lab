"""Lightweight HTTP API server wrapping Open Figure Lab CLI."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent.parent
CLI_MODULE = "open_figure_lab.cli"
DEFAULT_PORT = 8080
DEFAULT_PROJECT_NAME = "soc_proxy_fig2"
DEFAULT_PROJECT = ROOT / "examples" / DEFAULT_PROJECT_NAME
SESSION_CONFIG_PATH = ROOT / ".omx" / "open-figure-lab-session.json"
RUNS_DIR = ROOT / ".omx" / "runs"
_RUN_RECORD_LOCK = threading.RLock()
DEFAULT_MODEL_OPTION = {"id": "default", "label": "Default (CLI config)"}
AGENT_CACHE_TTL_SECONDS = 60
_AGENT_CACHE: dict[str, object] = {"expires_at": 0.0, "agents": []}
AGENT_DEFS = [
    {
        "id": "opencode",
        "name": "OpenCode",
        "bin": "opencode",
        "version_args": ["--version"],
        "models_args": ["models"],
        "fallback_models": [
            DEFAULT_MODEL_OPTION,
            {"id": "opencode/minimax-m2.5-free", "label": "opencode/minimax-m2.5-free"},
        ],
    },
    {
        "id": "claude",
        "name": "Claude Code",
        "bin": "claude",
        "fallback_bins": ["openclaude"],
        "version_args": ["--version"],
        "fallback_models": [
            DEFAULT_MODEL_OPTION,
            {"id": "sonnet", "label": "Sonnet (alias)"},
            {"id": "opus", "label": "Opus (alias)"},
            {"id": "haiku", "label": "Haiku (alias)"},
        ],
    },
    {
        "id": "codex",
        "name": "Codex CLI",
        "bin": "codex",
        "version_args": ["--version"],
        "fallback_models": [
            DEFAULT_MODEL_OPTION,
            {"id": "gpt-5.5", "label": "gpt-5.5"},
            {"id": "gpt-5.4", "label": "gpt-5.4"},
            {"id": "gpt-5.4-mini", "label": "gpt-5.4-mini"},
            {"id": "gpt-5.3-codex", "label": "gpt-5.3-codex"},
        ],
        "reasoning_options": [
            {"id": "default", "label": "Default"},
            {"id": "low", "label": "Low"},
            {"id": "medium", "label": "Medium"},
            {"id": "high", "label": "High"},
            {"id": "xhigh", "label": "XHigh"},
        ],
    },
    {
        "id": "cursor-agent",
        "name": "Cursor Agent",
        "bin": "cursor-agent",
        "version_args": ["--version"],
        "models_args": ["models"],
        "fallback_models": [
            DEFAULT_MODEL_OPTION,
        ],
    },
    {
        "id": "gemini",
        "name": "Gemini CLI",
        "bin": "gemini",
        "version_args": ["--version"],
        "fallback_models": [
            DEFAULT_MODEL_OPTION,
            {"id": "gemini-3-pro", "label": "gemini-3-pro"},
            {"id": "gemini-2.5-pro", "label": "gemini-2.5-pro"},
            {"id": "gemini-2.5-flash", "label": "gemini-2.5-flash"},
        ],
    },
]


def _load_session_config() -> dict:
    """Load session config from disk, returning defaults if missing."""
    if SESSION_CONFIG_PATH.exists():
        try:
            return json.loads(SESSION_CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"project": DEFAULT_PROJECT_NAME}


def _save_session_config(config: dict) -> None:
    """Persist session config to disk."""
    SESSION_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def _get_current_project_name() -> str:
    """Return the active project name from session config."""
    project_name = _load_session_config().get("project", DEFAULT_PROJECT_NAME)
    return project_name if _is_valid_project(project_name) else DEFAULT_PROJECT_NAME


def _get_project_root() -> Path:
    """Return the current project root directory."""
    return ROOT / "examples" / _get_current_project_name()


def _scan_projects() -> list[dict]:
    """Scan examples/ for figure projects containing spec/figure.yaml."""
    examples_dir = ROOT / "examples"
    projects = []
    if not examples_dir.is_dir():
        return projects
    for child in sorted(examples_dir.iterdir()):
        if child.is_dir() and (child / "spec" / "figure.yaml").exists():
            projects.append({"name": child.name, "path": str(child)})
    return projects


def _is_valid_project(project_name: str) -> bool:
    """Check whether project_name corresponds to a valid figure project."""
    if not project_name or "/" in project_name or "\\" in project_name or ".." in project_name:
        return False
    return (ROOT / "examples" / project_name / "spec" / "figure.yaml").exists()


def _generate_run_id() -> str:
    """Generate a URL-safe unique run identifier."""
    return uuid.uuid4().hex[:16]


def _save_run(run: dict) -> None:
    """Persist a run record to .omx/runs/<id>.json."""
    with _RUN_RECORD_LOCK:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        path = RUNS_DIR / f"{run['id']}.json"
        path.write_text(json.dumps(run, indent=2), encoding="utf-8")


def _normalize_run_record(run: dict) -> dict:
    """Backfill fields expected by current run consumers."""
    run.setdefault("fileChanges", [])
    run.setdefault("verificationStatus", "not_run")
    run.setdefault("verificationSteps", [])
    run.setdefault("qaReportPath", None)
    run.setdefault("events", [])
    return run


def _load_run(run_id: str) -> dict | None:
    """Load a run record from disk, or None if not found."""
    # Reject any path traversal
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        return None
    path = RUNS_DIR / f"{run_id}.json"
    with _RUN_RECORD_LOCK:
        if not path.exists():
            return None
        try:
            return _normalize_run_record(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return None


MAX_PROMPT_LENGTH = 8000
OPENCODE_RUN_TIMEOUT = 180  # seconds

_OPENCODE_BOUNDARY = (
    "IMPORTANT BOUNDARIES — you must follow these rules:\n"
    "- Do NOT fabricate or invent any scientific data, metrics, p-values, or results.\n"
    "- Do NOT modify files under data/ unless the user explicitly asks.\n"
    "- Prefer modifying spec/figure.yaml, src/render.py, and outputs/ artifacts.\n"
    "- When done, list every file you changed.\n"
)

SUPPORTED_AGENT_IDS = {"opencode", "claude", "codex"}

# --- Skill Registry ---

SKILL_REGISTRY: dict[str, dict] = {
    "open-figure-lab-core": {
        "id": "open-figure-lab-core",
        "title": "Open Figure Lab Core",
        "description": "Core scientific figure production rules for Open Figure Lab. Enforces data safety, reproducibility, and the canonical workflow.",
        "promptText": (
            "You are working in Open Figure Lab, a local-first scientific figure production system.\n"
            "The canonical workflow is: data -> figure spec -> skill renderer -> QA report -> revision diff -> export.\n"
            "Key files in this project:\n"
            "- spec/figure.yaml: the figure specification\n"
            "- spec/data_manifest.yaml or data/: data sources\n"
            "- outputs/preview.svg: rendered figure preview\n"
            "- outputs/qa_report.md: QA validation results\n"
            "\n"
            "SAFETY RULES (MANDATORY):\n"
            "- Do NOT fabricate or invent any scientific data, metrics, p-values, AUC, correlations, or statistical results.\n"
            "- Do NOT modify files under data/ unless the user explicitly asks.\n"
            "- All figure modifications must be reproducible from the spec and data.\n"
            "- When done, list every file you changed.\n"
        ),
        "source": "builtin",
        "enabled": True,
    },
    "scientific-figure-qa": {
        "id": "scientific-figure-qa",
        "title": "Scientific Figure QA",
        "description": "QA constraints for scientific figures: axis labels, legends, statistical annotations, journal compliance.",
        "promptText": (
            "SCIENTIFIC FIGURE QA RULES:\n"
            "- Ensure all axes have clear, descriptive labels with units where applicable.\n"
            "- Legends must be readable and not overlap data elements.\n"
            "- Statistical annotations (p-values, CI, n) must come from the data, never invented.\n"
            "- Check journal preset compliance (font sizes, margins, figure dimensions).\n"
            "- Verify color accessibility for colorblind readers.\n"
            "- After changes, run the QA check and report any failures.\n"
        ),
        "source": "builtin",
        "enabled": True,
    },
    "nature-style-figure": {
        "id": "nature-style-figure",
        "title": "Nature Style Figure",
        "description": "Nature journal formatting requirements: typography, sizing, multi-panel layout, export standards.",
        "promptText": (
            "NATURE JOURNAL FIGURE STYLE:\n"
            "- Use Arial or Helvetica font family, 5-7pt axis labels, 8-10pt titles.\n"
            "- Multi-panel figures should use consistent spacing and alignment.\n"
            "- Export at 300+ DPI for raster, vector formats preferred (SVG/PDF).\n"
            "- Figure width: 89mm (single) or 183mm (double) per Nature guidelines.\n"
            "- Minimize chartjunk; maximize data-ink ratio.\n"
            "- Use Nature's recommended color palette for accessibility.\n"
        ),
        "source": "builtin",
        "enabled": False,
    },
}


def _get_enabled_skills(skill_ids: list[str] | None = None) -> list[dict]:
    """Return skills to inject. If skill_ids is None, return enabled defaults."""
    if skill_ids is None:
        return [s for s in SKILL_REGISTRY.values() if s.get("enabled", False)]
    result = []
    for sid in skill_ids:
        skill = SKILL_REGISTRY.get(sid)
        if skill is None:
            return []  # Signal invalid
        result.append(skill)
    return result


def _build_injected_prompt(project_name: str, user_prompt: str, skills: list[dict]) -> str:
    """Build the full prompt with skill injection and project context."""
    project_dir = ROOT / "examples" / project_name

    parts: list[str] = []

    # Project context header
    parts.append(f"=== PROJECT: {project_name} ===")
    parts.append(f"Project directory: {project_dir}")
    parts.append("Key files:")
    parts.append(f"  - {project_dir / 'spec' / 'figure.yaml'}")
    parts.append(f"  - {project_dir / 'spec' / 'data_manifest.yaml'}")
    parts.append(f"  - {project_dir / 'outputs'}")
    parts.append("")

    # Inject skill prompts
    for skill in skills:
        parts.append(f"=== SKILL: {skill['title']} ===")
        parts.append(skill["promptText"])
        parts.append("")

    # User prompt
    parts.append("=== YOUR TASK ===")
    parts.append(user_prompt)

    return "\n".join(parts)


def _build_agent_cmd(agent_id: str, model: str, reasoning: str, cwd: Path) -> tuple[list[str], bool]:
    """Build argv and return (cmd, promptViaStdin)."""
    if agent_id == "opencode":
        cmd = ["opencode", "run", "--dangerously-skip-permissions"]
        if model != "default":
            cmd += ["--model", model]
        return cmd, False

    if agent_id == "claude":
        cmd = [
            "claude", "-p", "--output-format", "stream-json", "--verbose",
            "--permission-mode", "bypassPermissions",
        ]
        if model != "default":
            cmd += ["--model", model]
        return cmd, True

    if agent_id == "codex":
        cmd = [
            "codex", "exec", "--json", "--skip-git-repo-check",
            "--sandbox", "workspace-write",
            "-c", "sandbox_workspace_write.network_access=true",
            "-C", str(cwd),
        ]
        if model != "default":
            cmd += ["--model", model]
        if reasoning != "default":
            cmd += ["-c", f"model_reasoning_effort={reasoning}"]
        return cmd, True

    raise ValueError(f"Unknown agent: {agent_id}")


# --- File snapshot and change detection ---

_IGNORED_DIR_NAMES = {"__pycache__", ".git", "history"}
_IGNORED_FILE_NAMES = {".DS_Store", "Thumbs.db"}


def _should_ignore(relpath: str) -> bool:
    """Return True if this relative path should be excluded from snapshots."""
    parts = relpath.replace("\\", "/").split("/")
    # Ignore directories by name
    for part in parts[:-1]:
        if part in _IGNORED_DIR_NAMES:
            return True
    # Ignore specific files
    if parts[-1] in _IGNORED_FILE_NAMES:
        return True
    # Ignore outputs/*.tmp
    if len(parts) >= 2 and parts[0] == "outputs" and parts[-1].endswith(".tmp"):
        return True
    return False


def _file_fingerprint(path: Path) -> tuple[int, int, str]:
    """Return (size, mtime_ns, sha256_hex_prefix) for a file."""
    stat = path.stat()
    size = stat.st_size
    mtime_ns = stat.st_mtime_ns
    # SHA-256 of first 1MB
    h = hashlib.sha256()
    remaining = 1024 * 1024
    with open(path, "rb") as f:
        while remaining > 0:
            chunk = f.read(min(8192, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    return size, mtime_ns, h.hexdigest()[:16]


def _snapshot_project(project_dir: Path) -> dict[str, tuple[int, int, str]]:
    """Scan project_dir and return {relpath: (size, mtime_ns, sha256_prefix)}."""
    snapshot: dict[str, tuple[int, int, str]] = {}
    if not project_dir.is_dir():
        return snapshot
    for fpath in project_dir.rglob("*"):
        if not fpath.is_file():
            continue
        relpath = str(fpath.relative_to(project_dir)).replace("\\", "/")
        if _should_ignore(relpath):
            continue
        try:
            snapshot[relpath] = _file_fingerprint(fpath)
        except OSError:
            continue  # file may vanish during scan
    return snapshot


def _compute_file_changes(
    before: dict[str, tuple[int, int, str]],
    after: dict[str, tuple[int, int, str]],
) -> list[dict[str, str]]:
    """Compare two snapshots and return a list of {path, status} dicts."""
    changes: list[dict[str, str]] = []
    before_keys = set(before.keys())
    after_keys = set(after.keys())

    for path in sorted(after_keys - before_keys):
        changes.append({"path": path, "status": "added"})

    for path in sorted(before_keys - after_keys):
        changes.append({"path": path, "status": "deleted"})

    for path in sorted(before_keys & after_keys):
        if before[path] != after[path]:
            changes.append({"path": path, "status": "modified"})

    return changes

# Registry of currently-running Popen objects keyed by run_id.
_RUN_PROCESSES: dict[str, subprocess.Popen] = {}
_RUN_PROCESSES_LOCK = threading.Lock()

# Global counter for sequential event IDs (per run, but monotonic is fine).
_EVENT_ID_COUNTER = 0
_EVENT_ID_LOCK = threading.Lock()


def _next_event_id() -> int:
    """Return a monotonically increasing event ID."""
    global _EVENT_ID_COUNTER
    with _EVENT_ID_LOCK:
        _EVENT_ID_COUNTER += 1
        return _EVENT_ID_COUNTER


def _is_valid_agent_model(agent_id: str, model: str) -> bool:
    """Check whether model is 'default' or one returned by the given agent's adapter."""
    if model == "default":
        return True
    if not model or any(c in model for c in "\x00\x0a\x0d"):
        return False

    agents = _cached_agents()
    agent = next((a for a in agents if a.get("id") == agent_id), None)
    if not agent:
        return False
    return any(item.get("id") == model for item in agent.get("models", []))


def _run_agent_background(run_id: str, project_dir: Path, agent_id: str,
                          model: str, reasoning: str, full_prompt: str) -> None:
    """Execute an agent in a background thread using Popen, streaming stdout/stderr into run events."""
    # --- Extract project name from directory ---
    project_name = project_dir.name

    # --- Take snapshot before run ---
    snapshot_before = _snapshot_project(project_dir)

    try:
        cmd, prompt_via_stdin = _build_agent_cmd(agent_id, model, reasoning, project_dir)
        # For agents that take prompt in argv (not stdin), append it now
        if not prompt_via_stdin:
            cmd.append(full_prompt)
    except ValueError as exc:
        run = _load_run(run_id)
        if run is not None:
            run["status"] = "failed"
            run["returncode"] = -1
            run["stderr"] = str(exc)
            run["completedAt"] = datetime.now(timezone.utc).isoformat()
            _save_run(run)
        return

    run = _load_run(run_id)
    if run is None:
        return

    # Mark as running
    now = datetime.now(timezone.utc).isoformat()
    run["status"] = "running"
    run["command"] = cmd
    run["adapter"] = {"id": agent_id, "command": cmd[0], "promptViaStdin": prompt_via_stdin}
    run["startedAt"] = now
    run["events"].append({"id": _next_event_id(), "ts": now, "type": "running", "detail": "Agent started"})
    _save_run(run)

    # Check if already cancelled before spawning
    run = _load_run(run_id)
    if run is not None and run["status"] == "cancelled":
        return

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def _finalize_run(status: str, returncode: int) -> None:
        """Snapshot files, compute changes, and finalize the run record."""
        snapshot_after = _snapshot_project(project_dir)
        file_changes = _compute_file_changes(snapshot_before, snapshot_after)

        run = _load_run(run_id)
        if run is None:
            return
        run["returncode"] = returncode
        run["stdout"] = "\n".join(stdout_lines)[-4000:]
        run["stderr"] = "\n".join(stderr_lines)[-4000:]
        run["fileChanges"] = file_changes
        if file_changes:
            run["events"].append({
                "id": _next_event_id(),
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": "file_changes",
                "detail": json.dumps(file_changes),
            })
        _save_run(run)

        # --- Post-run verification (only on agent success) ---
        if status == "completed" and returncode == 0:
            run = _load_run(run_id)
            if run is None:
                return
            run["verificationStatus"] = "running"
            run["events"].append({
                "id": _next_event_id(),
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": "verification_started",
                "detail": "Starting post-run verification: validate -> render -> qa",
            })
            _save_run(run)

            verification = _run_verification_steps(project_name, run_id)

            run = _load_run(run_id)
            if run is None:
                return
            run["verificationStatus"] = verification["overall"]
            run["verificationSteps"] = verification["steps"]
            run["qaReportPath"] = verification["qaReportPath"]

            ver_status = verification["overall"]
            run["events"].append({
                "id": _next_event_id(),
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": f"verification_{ver_status}",
                "detail": json.dumps({
                    "overall": ver_status,
                    "steps": [{"name": s["name"], "success": s["success"]} for s in verification["steps"]],
                }),
            })
            _save_run(run)
        else:
            # Agent failed: no verification.
            run = _load_run(run_id)
            if run is not None:
                run["verificationStatus"] = "not_run"
                run["verificationSteps"] = []
                run["qaReportPath"] = None
                _save_run(run)

        run = _load_run(run_id)
        if run is None:
            return
        run["status"] = status
        run["completedAt"] = datetime.now(timezone.utc).isoformat()
        run["events"].append({
            "id": _next_event_id(),
            "ts": run["completedAt"],
            "type": status,
            "detail": f"exit={returncode}",
        })
        _save_run(run)

    try:
        # On Windows, CREATE_NEW_PROCESS_GROUP allows us to send CTRL_BREAK later.
        popen_kwargs: dict = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "cwd": str(project_dir),
        }
        if prompt_via_stdin:
            popen_kwargs["stdin"] = subprocess.PIPE
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen(cmd, **popen_kwargs)

        # If prompt goes via stdin, write and close immediately
        if prompt_via_stdin and proc.stdin:
            try:
                proc.stdin.write(full_prompt)
                proc.stdin.close()
            except OSError:
                pass  # process may have exited

        with _RUN_PROCESSES_LOCK:
            _RUN_PROCESSES[run_id] = proc

        # Read stdout and stderr line by line (interleaved via threads).
        def _read_stream(stream, lines, evt_type):
            for line in stream:
                line = line.rstrip("\n\r")
                if not line:
                    continue
                lines.append(line)
                run = _load_run(run_id)
                if run is None:
                    return
                # Re-check cancellation
                if run["status"] == "cancelled":
                    return
                ts = datetime.now(timezone.utc).isoformat()
                run["events"].append({
                    "id": _next_event_id(),
                    "ts": ts,
                    "type": evt_type,
                    "detail": line[-2000:],  # truncate very long lines
                })
                # Keep only last 4000 chars in aggregate fields
                run["stdout"] = "\n".join(stdout_lines)[-4000:]
                run["stderr"] = "\n".join(stderr_lines)[-4000:]
                _save_run(run)

        t_out = threading.Thread(target=_read_stream, args=(proc.stdout, stdout_lines, "stdout"), daemon=True)
        t_err = threading.Thread(target=_read_stream, args=(proc.stderr, stderr_lines, "stderr"), daemon=True)
        t_out.start()
        t_err.start()

        proc.wait()
        t_out.join(timeout=5)
        t_err.join(timeout=5)

        returncode = proc.returncode

        # Clean up process registry
        with _RUN_PROCESSES_LOCK:
            _RUN_PROCESSES.pop(run_id, None)

        # Reload after threads finished
        run = _load_run(run_id)
        if run is None:
            return

        # If cancelled while running, don't overwrite status but still record file changes
        if run["status"] == "cancelled":
            snapshot_after = _snapshot_project(project_dir)
            file_changes = _compute_file_changes(snapshot_before, snapshot_after)
            run["fileChanges"] = file_changes
            run["completedAt"] = datetime.now(timezone.utc).isoformat()
            if file_changes:
                run["events"].append({
                    "id": _next_event_id(),
                    "ts": run["completedAt"],
                    "type": "file_changes",
                    "detail": json.dumps(file_changes),
                })
            _save_run(run)
            return

        final_status = "completed" if returncode == 0 else "failed"
        _finalize_run(final_status, returncode)

    except Exception as exc:
        with _RUN_PROCESSES_LOCK:
            _RUN_PROCESSES.pop(run_id, None)

        run = _load_run(run_id)
        if run is None:
            return
        if run["status"] == "cancelled":
            snapshot_after = _snapshot_project(project_dir)
            file_changes = _compute_file_changes(snapshot_before, snapshot_after)
            run["fileChanges"] = file_changes
            run["completedAt"] = datetime.now(timezone.utc).isoformat()
            _save_run(run)
            return

        # Still record file changes even on exception
        snapshot_after = _snapshot_project(project_dir)
        file_changes = _compute_file_changes(snapshot_before, snapshot_after)
        run["returncode"] = -1
        run["stdout"] = "\n".join(stdout_lines)[-4000:]
        run["stderr"] = str(exc)
        run["status"] = "failed"
        run["completedAt"] = datetime.now(timezone.utc).isoformat()
        run["fileChanges"] = file_changes
        run["events"].append({
            "id": _next_event_id(),
            "ts": run["completedAt"],
            "type": "failed",
            "detail": str(exc),
        })
        if file_changes:
            run["events"].append({
                "id": _next_event_id(),
                "ts": run["completedAt"],
                "type": "file_changes",
                "detail": json.dumps(file_changes),
            })
        _save_run(run)


def _cli_env() -> dict[str, str]:
    """Return environment dict with PYTHONPATH set to include src/."""
    env = os.environ.copy()
    src_dir = str(ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_dir if not existing else f"{src_dir}{os.pathsep}{existing}"
    return env


def _run_cli(args: list[str]) -> tuple[int, str, str]:
    """Run the CLI as a subprocess and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "-m", CLI_MODULE] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, env=_cli_env())
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _run_verification_steps(project_name: str, run_id: str) -> dict:
    """Run validate -> render -> qa sequentially and return verification result.

    Returns a dict with keys:
      - overall: "passed" | "failed"
      - steps: list of {name, success, stdout, stderr, returncode}
      - qaReportPath: relative path to qa_report.md (or None)
    """
    steps: list[dict] = []
    all_passed = True
    qa_report_path = None

    for step_name in ("validate", "render", "qa"):
        # Update run record with current verification step
        run = _load_run(run_id)
        if run is not None:
            ts = datetime.now(timezone.utc).isoformat()
            run["events"].append({
                "id": _next_event_id(),
                "ts": ts,
                "type": "verification_step",
                "detail": json.dumps({"step": step_name, "status": "running"}),
            })
            _save_run(run)

        try:
            returncode, stdout, stderr = _run_cli([step_name, f"examples/{project_name}"])
        except Exception as exc:
            returncode, stdout, stderr = -1, "", str(exc)
        success = returncode == 0

        step_result = {
            "name": step_name,
            "success": success,
            "stdout": stdout[-2000:],  # truncate
            "stderr": stderr[-2000:],
            "returncode": returncode,
        }
        steps.append(step_result)

        if not success:
            all_passed = False

        # Record step completion event
        run = _load_run(run_id)
        if run is not None:
            ts = datetime.now(timezone.utc).isoformat()
            run["events"].append({
                "id": _next_event_id(),
                "ts": ts,
                "type": "verification_step",
                "detail": json.dumps({
                    "step": step_name,
                    "status": "passed" if success else "failed",
                    "returncode": returncode,
                }),
            })
            _save_run(run)

        # Stop on first failure
        if not success:
            break

    # Determine qa_report path
    qa_path = ROOT / "examples" / project_name / "outputs" / "qa_report.md"
    if qa_path.exists():
        qa_report_path = f"examples/{project_name}/outputs/qa_report.md"

    return {
        "overall": "passed" if all_passed else "failed",
        "steps": steps,
        "qaReportPath": qa_report_path,
    }


def _read_text(path: Path) -> str | None:
    """Read a text file, or None if missing."""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _run_probe(command: str, args: list[str], timeout: float = 3.0) -> tuple[int, str, str]:
    """Run a short CLI probe without failing the HTTP request."""
    try:
        proc = subprocess.run(
            [command] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:
        return 1, "", str(exc)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _parse_line_models(stdout: str, fallback: list[dict]) -> list[dict]:
    """Parse one-model-id-per-line output, matching OpenDesign's basic model picker shape."""
    seen = {"default"}
    models = [DEFAULT_MODEL_OPTION]
    for raw in stdout.splitlines():
        model_id = raw.strip()
        if not model_id or model_id.startswith("#") or model_id in seen:
            continue
        seen.add(model_id)
        models.append({"id": model_id, "label": model_id})
    if len(models) == 1:
        return fallback
    return models


def _detect_agents() -> list[dict]:
    """Detect local coding-agent CLIs in the same spirit as OpenDesign's adapter picker."""
    detected: list[dict] = []
    for agent_def in AGENT_DEFS:
        candidates = [agent_def["bin"]] + agent_def.get("fallback_bins", [])
        executable = next((shutil.which(candidate) for candidate in candidates if shutil.which(candidate)), None)
        available = executable is not None
        version = None
        models = agent_def.get("fallback_models", [DEFAULT_MODEL_OPTION])

        if available:
            code, stdout, stderr = _run_probe(executable, agent_def.get("version_args", ["--version"]))
            version = stdout or stderr or ("available" if code == 0 else None)
            if agent_def.get("models_args"):
                model_code, model_stdout, _model_stderr = _run_probe(executable, agent_def["models_args"], timeout=5.0)
                if model_code == 0 and model_stdout:
                    models = _parse_line_models(model_stdout, models)

        detected.append({
            "id": agent_def["id"],
            "name": agent_def["name"],
            "bin": agent_def["bin"],
            "available": available,
            "path": executable,
            "version": version,
            "models": models,
            "reasoningOptions": agent_def.get("reasoning_options", []),
        })
    return detected


def _cached_agents(force: bool = False) -> list[dict]:
    """Return cached agent detection results so cold CLI probes do not block every UI request."""
    now = time.time()
    if not force and now < float(_AGENT_CACHE["expires_at"]):
        return list(_AGENT_CACHE["agents"])
    agents = _detect_agents()
    _AGENT_CACHE["agents"] = agents
    _AGENT_CACHE["expires_at"] = now + AGENT_CACHE_TTL_SECONDS
    return agents


class APIHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the Open Figure Lab API."""

    def _set_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    def _text_response(self, text: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    def _serve_frontend(self) -> None:
        frontend = ROOT / "app" / "web-ui" / "index.html"
        if frontend.exists():
            content = frontend.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._set_cors()
            self.end_headers()
            self.wfile.write(content)
        else:
            self._text_response("Frontend not found", 404)

    def _serve_static_file(self, filename: str, content_type: str) -> None:
        file_path = ROOT / "app" / "web-ui" / filename
        if file_path.exists():
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self._set_cors()
            self.end_headers()
            self.wfile.write(content)
        else:
            self._text_response(f"{filename} not found", 404)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._set_cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._serve_frontend()
        elif path == "/styles.css":
            self._serve_static_file("styles.css", "text/css")
        elif path == "/app.js":
            self._serve_static_file("app.js", "application/javascript")
        elif path == "/api/project":
            self._handle_get_project()
        elif path == "/api/projects":
            self._handle_get_projects()
        elif path == "/api/session-config":
            self._handle_get_session_config()
        elif path == "/api/agents":
            self._handle_get_agents(parsed.query)
        elif path == "/api/skills":
            self._handle_get_skills()
        elif path == "/api/spec":
            self._handle_get_spec()
        elif path == "/api/data-manifest":
            self._handle_get_data_manifest()
        elif path == "/api/qa-report":
            self._handle_get_qa_report()
        elif path.startswith("/outputs/"):
            self._handle_static_output(path)
        elif path.startswith("/api/agent-runs/") and path.endswith("/events"):
            self._handle_get_agent_run_events(path, parsed.query)
        elif path.startswith("/api/agent-runs/"):
            self._handle_get_agent_run(path)
        else:
            self._text_response("Not found", 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/validate":
            self._handle_validate()
        elif path == "/api/render":
            self._handle_render()
        elif path == "/api/qa":
            self._handle_qa()
        elif path == "/api/session-config":
            self._handle_post_session_config()
        elif path == "/api/agent-runs":
            self._handle_post_agent_run()
        elif path.startswith("/api/agent-runs/") and path.endswith("/cancel"):
            self._handle_cancel_agent_run(path)
        else:
            self._json_response({"error": "Not found"}, 404)

    # --- GET handlers ---

    def _handle_get_project(self) -> None:
        project = _get_project_root()
        self._json_response({
            "name": project.name,
            "path": str(project),
            "exists": project.exists(),
        })

    def _handle_get_projects(self) -> None:
        self._json_response({"projects": _scan_projects()})

    def _handle_get_session_config(self) -> None:
        config = _load_session_config()
        self._json_response(config)

    def _handle_post_session_config(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            incoming = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            self._json_response({"error": "Invalid JSON"}, 400)
            return

        config = _load_session_config()
        for key in ("project", "agentId", "model", "reasoning"):
            if key in incoming:
                config[key] = incoming[key]

        # Validate project exists
        project_name = config.get("project", DEFAULT_PROJECT_NAME)
        if not _is_valid_project(project_name):
            self._json_response({"error": f"Project '{project_name}' not found"}, 400)
            return

        _save_session_config(config)
        self._json_response({"ok": True, "config": config})

    def _read_json_body(self) -> tuple[dict | None, int]:
        """Read and parse JSON request body. Returns (data, error_status)."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            if not body:
                return {}, 0
            return json.loads(body), 0
        except (json.JSONDecodeError, ValueError):
            return None, 400

    def _handle_post_agent_run(self) -> None:
        """Create a new agent run record and start background execution."""
        data, err = self._read_json_body()
        if data is None:
            self._json_response({"error": "Invalid JSON"}, err)
            return

        # --- validate agentId ---
        agent_id = data.get("agentId", "")
        if agent_id not in SUPPORTED_AGENT_IDS:
            self._json_response({"error": f"Agent '{agent_id}' not supported. Choose from: {', '.join(sorted(SUPPORTED_AGENT_IDS))}"}, 400)
            return

        # --- validate project ---
        project = data.get("project", "")
        if not _is_valid_project(project):
            self._json_response({"error": f"Invalid project: {project!r}"}, 400)
            return

        # --- validate model ---
        model = data.get("model", "default")
        if not _is_valid_agent_model(agent_id, model):
            self._json_response({"error": f"Invalid model for {agent_id}: {model!r}"}, 400)
            return

        # --- validate prompt ---
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            self._json_response({"error": "Prompt must not be empty"}, 400)
            return
        if len(prompt) > MAX_PROMPT_LENGTH:
            self._json_response({"error": f"Prompt exceeds {MAX_PROMPT_LENGTH} character limit"}, 400)
            return

        reasoning = data.get("reasoning", "default")

        # --- validate and resolve skills ---
        skill_ids = data.get("skillIds")  # Optional: list of skill IDs or None for defaults
        if skill_ids is not None:
            if not isinstance(skill_ids, list):
                self._json_response({"error": "skillIds must be a list"}, 400)
                return
            for sid in skill_ids:
                if not isinstance(sid, str) or sid not in SKILL_REGISTRY:
                    self._json_response({"error": f"Invalid skill ID: {sid!r}"}, 400)
                    return

        skills = _get_enabled_skills(skill_ids)
        active_skill_ids = [s["id"] for s in skills]

        # --- build full prompt with skill injection ---
        full_prompt = _build_injected_prompt(project, prompt, skills)

        # --- create run record ---
        run_id = _generate_run_id()
        now = datetime.now(timezone.utc).isoformat()
        project_dir = ROOT / "examples" / project
        run: dict = {
            "id": run_id,
            "status": "pending",
            "agentId": agent_id,
            "model": model,
            "reasoning": reasoning,
            "project": project,
            "prompt": prompt,
            "skillIds": active_skill_ids,
            "injectedPromptPreview": full_prompt[:2000] + ("..." if len(full_prompt) > 2000 else ""),
            "createdAt": now,
            "command": [],
            "adapter": {},
            "startedAt": None,
            "completedAt": None,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "fileChanges": [],
            "verificationStatus": "not_run",
            "verificationSteps": [],
            "qaReportPath": None,
            "events": [
                {"id": _next_event_id(), "ts": now, "type": "created", "detail": "Run record created"},
            ],
        }
        _save_run(run)

        # --- launch background thread ---
        thread = threading.Thread(
            target=_run_agent_background,
            args=(run_id, project_dir, agent_id, model, reasoning, full_prompt),
            daemon=True,
        )
        thread.start()

        self._json_response(run, 202)

    def _handle_get_agent_run(self, path: str) -> None:
        """Return a single agent run record by id."""
        run_id = path.split("/api/agent-runs/", 1)[-1]
        run = _load_run(run_id)
        if run is None:
            self._json_response({"error": "Run not found"}, 404)
            return
        self._json_response(run)

    def _handle_get_agent_run_events(self, path: str, query: str) -> None:
        """SSE endpoint: stream run events as text/event-stream."""
        # path = /api/agent-runs/<id>/events
        parts = path.split("/")
        if len(parts) < 5:
            self._text_response("Invalid path", 400)
            return
        run_id = parts[3]

        # Parse ?after=<event_id>
        after_id = 0
        for param in query.split("&"):
            if param.startswith("after="):
                try:
                    after_id = int(param.split("=", 1)[1])
                except ValueError:
                    pass

        run = _load_run(run_id)
        if run is None:
            self._text_response("Run not found", 404)
            return

        # Filter events after the given ID
        events = [e for e in run.get("events", []) if e.get("id", 0) > after_id]

        # Build SSE response
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._set_cors()
        self.end_headers()

        for evt in events:
            data_str = json.dumps(evt)
            frame = f"id: {evt.get('id', 0)}\nevent: {evt.get('type', 'message')}\ndata: {data_str}\n\n"
            self.wfile.write(frame.encode("utf-8"))
        self.wfile.flush()

    def _handle_cancel_agent_run(self, path: str) -> None:
        """Cancel an agent run, terminating the process if still running."""
        # path = /api/agent-runs/<id>/cancel
        parts = path.split("/")
        # ['', 'api', 'agent-runs', '<id>', 'cancel']
        if len(parts) < 5:
            self._json_response({"error": "Invalid path"}, 400)
            return
        run_id = parts[3]
        run = _load_run(run_id)
        if run is None:
            self._json_response({"error": "Run not found"}, 404)
            return

        if run["status"] in ("completed", "failed", "cancelled"):
            self._json_response({"error": f"Run already {run['status']}"}, 409)
            return

        # Try to terminate the process if it's still running
        with _RUN_PROCESSES_LOCK:
            proc = _RUN_PROCESSES.get(run_id)
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
            except OSError:
                pass  # process already exited

        now = datetime.now(timezone.utc).isoformat()
        run["status"] = "cancelled"
        run["completedAt"] = now
        run["events"].append({
            "id": _next_event_id(),
            "ts": now,
            "type": "cancelled",
            "detail": "Cancelled by user",
        })
        _save_run(run)
        self._json_response(run)

    def _handle_get_agents(self, query: str = "") -> None:
        self._json_response({"agents": _cached_agents(force="refresh=1" in query)})

    def _handle_get_skills(self) -> None:
        """Return the skill registry."""
        skills = list(SKILL_REGISTRY.values())
        self._json_response({"skills": skills})

    def _handle_get_spec(self) -> None:
        spec_path = _get_project_root() / "spec" / "figure.yaml"
        content = _read_text(spec_path)
        if content is None:
            self._json_response({"error": "figure.yaml not found"}, 404)
        else:
            self._json_response({"content": content, "path": str(spec_path)})

    def _handle_get_data_manifest(self) -> None:
        manifest_path = _get_project_root() / "spec" / "data_manifest.yaml"
        content = _read_text(manifest_path)
        if content is None:
            self._json_response({"error": "data_manifest.yaml not found"}, 404)
        else:
            self._json_response({"content": content, "path": str(manifest_path)})

    def _handle_get_qa_report(self) -> None:
        report_path = _get_project_root() / "outputs" / "qa_report.md"
        content = _read_text(report_path)
        if content is None:
            self._json_response({"error": "qa_report.md not found"}, 404)
        else:
            self._json_response({"content": content, "path": str(report_path)})

    def _handle_static_output(self, path: str) -> None:
        filename = path.split("/outputs/", 1)[-1]
        file_path = (_get_project_root() / "outputs" / filename).resolve()
        if not file_path.is_relative_to((_get_project_root() / "outputs").resolve()):
            self._text_response("Forbidden", 403)
            return
        if not file_path.exists() or not file_path.is_file():
            self._text_response("File not found", 404)
            return

        suffix = file_path.suffix.lower()
        content_types = {
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".md": "text/markdown; charset=utf-8",
            ".txt": "text/plain; charset=utf-8",
        }
        ct = content_types.get(suffix, "application/octet-stream")
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self._set_cors()
        self.end_headers()
        self.wfile.write(data)

    # --- POST handlers ---

    def _handle_validate(self) -> None:
        project = _get_project_root()
        code, stdout, stderr = _run_cli(["validate", str(project)])
        self._json_response({
            "success": code == 0,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": code,
        })

    def _handle_render(self) -> None:
        project = _get_project_root()
        code, stdout, stderr = _run_cli(["render", str(project)])
        self._json_response({
            "success": code == 0,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": code,
        })

    def _handle_qa(self) -> None:
        project = _get_project_root()
        code, stdout, stderr = _run_cli(["qa", str(project)])
        self._json_response({
            "success": code == 0,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": code,
        })

    def log_message(self, format: str, *args: object) -> None:
        print(f"[OFL API] {args[0]}")


def run_server(host: str = "localhost", port: int = DEFAULT_PORT) -> None:
    """Start the API server."""
    server = ThreadingHTTPServer((host, port), APIHandler)
    print(f"Open Figure Lab API server running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    run_server()
