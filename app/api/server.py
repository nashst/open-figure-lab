"""Lightweight HTTP API server wrapping Open Figure Lab CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent.parent
CLI_MODULE = "open_figure_lab.cli"
DEFAULT_PORT = 8080
DEFAULT_PROJECT = ROOT / "examples" / "soc_proxy_fig2"


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


def _read_yaml(path: Path) -> dict | None:
    """Read a YAML file and return parsed content as dict, or None if missing."""
    if not path.exists():
        return None
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except ImportError:
        return {"raw": path.read_text(encoding="utf-8")}


def _read_text(path: Path) -> str | None:
    """Read a text file, or None if missing."""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


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

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._set_cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/project":
            self._handle_get_project()
        elif path == "/api/spec":
            self._handle_get_spec()
        elif path == "/api/data-manifest":
            self._handle_get_data_manifest()
        elif path == "/api/qa-report":
            self._handle_get_qa_report()
        elif path.startswith("/outputs/"):
            self._handle_static_output(path)
        else:
            self._serve_frontend()

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

    def _handle_get_spec(self) -> None:
        spec_path = _get_project_root() / "spec" / "figure.yaml"
        content = _read_yaml(spec_path)
        if content is None:
            self._json_response({"error": "figure.yaml not found"}, 404)
        else:
            self._json_response({"content": content, "path": str(spec_path)})

    def _handle_get_data_manifest(self) -> None:
        manifest_path = _get_project_root() / "spec" / "data_manifest.yaml"
        content = _read_yaml(manifest_path)
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
    server = HTTPServer((host, port), APIHandler)
    print(f"Open Figure Lab API server running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    run_server()
