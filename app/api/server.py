"""Lightweight HTTP API server wrapping Open Figure Lab CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent.parent
CLI_MODULE = "open_figure_lab.cli"
DEFAULT_PORT = 8080
DEFAULT_PROJECT = ROOT / "examples" / "soc_proxy_fig2"
DEFAULT_MODEL_OPTION = {"id": "default", "label": "Default (CLI config)"}
AGENT_CACHE_TTL_SECONDS = 60
_AGENT_CACHE: dict[str, object] = {"expires_at": 0.0, "agents": []}
AGENT_DEFS = [
    {
        "id": "opencode",
        "name": "Sisyphus - Ultraworker",
        "bin": "opencode",
        "version_args": ["--version"],
        "models_args": ["models"],
        "preferred_model": "xiaomi-token-plan-cn/mimo-v2.5-pro",
        "preferred_reasoning": "high",
        "model_labels": {
            "xiaomi-token-plan-cn/mimo-v2.5-pro": "MiMo-V2.5-Pro Xiaomi Token Plan (China)",
        },
        "fallback_models": [
            DEFAULT_MODEL_OPTION,
            {
                "id": "xiaomi-token-plan-cn/mimo-v2.5-pro",
                "label": "MiMo-V2.5-Pro Xiaomi Token Plan (China)",
            },
        ],
        "reasoning_options": [
            {"id": "default", "label": "Default"},
            {"id": "low", "label": "Low"},
            {"id": "medium", "label": "Medium"},
            {"id": "high", "label": "High"},
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


def _get_project_root() -> Path:
    """Return the current project root directory."""
    return DEFAULT_PROJECT


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


def _parse_line_models(stdout: str, fallback: list[dict], labels: dict[str, str] | None = None) -> list[dict]:
    """Parse one-model-id-per-line output, matching OpenDesign's basic model picker shape."""
    labels = labels or {}
    seen = {"default"}
    models = [DEFAULT_MODEL_OPTION]
    for raw in stdout.splitlines():
        model_id = raw.strip()
        if not model_id or model_id.startswith("#") or model_id in seen:
            continue
        seen.add(model_id)
        models.append({"id": model_id, "label": labels.get(model_id, model_id)})
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
                    models = _parse_line_models(model_stdout, models, agent_def.get("model_labels"))

        detected.append({
            "id": agent_def["id"],
            "name": agent_def["name"],
            "bin": agent_def["bin"],
            "available": available,
            "path": executable,
            "version": version,
            "models": models,
            "preferredModel": agent_def.get("preferred_model"),
            "preferredReasoning": agent_def.get("preferred_reasoning"),
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
