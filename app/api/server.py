"""Lightweight HTTP API server wrapping Open Figure Lab CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{run['id']}.json"
    path.write_text(json.dumps(run, indent=2), encoding="utf-8")


def _load_run(run_id: str) -> dict | None:
    """Load a run record from disk, or None if not found."""
    # Reject any path traversal
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        return None
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


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
        elif path == "/api/spec":
            self._handle_get_spec()
        elif path == "/api/data-manifest":
            self._handle_get_data_manifest()
        elif path == "/api/qa-report":
            self._handle_get_qa_report()
        elif path.startswith("/outputs/"):
            self._handle_static_output(path)
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
        """Create a new agent run record."""
        data, err = self._read_json_body()
        if data is None:
            self._json_response({"error": "Invalid JSON"}, err)
            return

        project = data.get("project", "")
        if not _is_valid_project(project):
            self._json_response({"error": f"Invalid project: {project!r}"}, 400)
            return

        run_id = _generate_run_id()
        now = datetime.now(timezone.utc).isoformat()
        run = {
            "id": run_id,
            "status": "pending",
            "agentId": data.get("agentId", ""),
            "model": data.get("model", "default"),
            "reasoning": data.get("reasoning", "default"),
            "project": project,
            "prompt": data.get("prompt", ""),
            "createdAt": now,
            "events": [
                {"ts": now, "type": "created", "detail": "Run record created"},
            ],
        }
        _save_run(run)
        self._json_response(run, 201)

    def _handle_get_agent_run(self, path: str) -> None:
        """Return a single agent run record by id."""
        run_id = path.split("/api/agent-runs/", 1)[-1]
        run = _load_run(run_id)
        if run is None:
            self._json_response({"error": "Run not found"}, 404)
            return
        self._json_response(run)

    def _handle_cancel_agent_run(self, path: str) -> None:
        """Cancel an agent run."""
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

        if run["status"] in ("completed", "cancelled"):
            self._json_response({"error": f"Run already {run['status']}"}, 409)
            return

        now = datetime.now(timezone.utc).isoformat()
        run["status"] = "cancelled"
        run["events"].append({"ts": now, "type": "cancelled", "detail": "Cancelled by user"})
        _save_run(run)
        self._json_response(run)

    def _handle_get_agents(self, query: str = "") -> None:
        self._json_response({"agents": _cached_agents(force="refresh=1" in query)})

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
