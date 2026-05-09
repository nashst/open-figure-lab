"""Tests for the async agent-run API with SSE support."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import HTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock, patch
from urllib.request import Request, urlopen

# Ensure the app package is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from api.server import (  # noqa: E402
    RUNS_DIR,
    _build_agent_cmd,
    _compute_file_changes,
    _generate_run_id,
    _is_valid_agent_model,
    _is_valid_project,
    _load_run,
    _save_run,
    _snapshot_project,
    APIHandler,
)

VALID_PROJECT = "soc_proxy_fig2"


def _free_port() -> int:
    """Return an available localhost port."""
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_mock_popen(stdout_lines: list[str] | None = None,
                     stderr_lines: list[str] | None = None,
                     returncode: int = 0,
                     block_event: threading.Event | None = None) -> MagicMock:
    """Build a MagicMock that behaves like Popen for streaming tests.

    If block_event is provided, the mock will wait on it before completing,
    allowing tests to cancel while the "process" is still running.
    """
    proc = MagicMock()
    proc.returncode = returncode

    stdout_lines = stdout_lines or []
    stderr_lines = stderr_lines or []

    proc.stdout = io.StringIO("\n".join(stdout_lines) + "\n" if stdout_lines else "")
    proc.stderr = io.StringIO("\n".join(stderr_lines) + "\n" if stderr_lines else "")

    # poll() returns None while "running", then returncode after wait()
    _finished = threading.Event()

    def _poll():
        if _finished.is_set():
            return returncode
        return None

    proc.poll.side_effect = _poll

    def _wait(timeout=None):
        if block_event is not None:
            block_event.wait(timeout=timeout)
        _finished.set()
        return returncode

    proc.wait.side_effect = _wait
    proc.terminate = MagicMock(side_effect=lambda: _finished.set())
    proc.kill = MagicMock(side_effect=lambda: _finished.set())
    return proc


class _QuietHandler(APIHandler):
    """Suppress log noise during tests."""

    def log_message(self, format: str, *args: object) -> None:
        pass  # pragma: no cover


class RunHelpersTests(unittest.TestCase):
    """Unit tests for pure helper functions."""

    def test_generate_run_id_format(self) -> None:
        rid = _generate_run_id()
        self.assertEqual(len(rid), 16)
        self.assertTrue(rid.isalnum())

    def test_generate_run_id_unique(self) -> None:
        ids = {_generate_run_id() for _ in range(50)}
        self.assertEqual(len(ids), 50)

    def test_is_valid_project_ok(self) -> None:
        self.assertTrue(_is_valid_project(VALID_PROJECT))

    def test_is_valid_project_rejects_empty(self) -> None:
        self.assertFalse(_is_valid_project(""))

    def test_is_valid_project_rejects_traversal(self) -> None:
        self.assertFalse(_is_valid_project("../etc"))
        self.assertFalse(_is_valid_project("foo/bar"))

    def test_is_valid_project_rejects_unknown(self) -> None:
        self.assertFalse(_is_valid_project("nonexistent_project_xyz"))

    def test_save_and_load_run(self) -> None:
        run = {
            "id": _generate_run_id(),
            "status": "pending",
            "agentId": "opencode",
            "model": "default",
            "reasoning": "default",
            "project": VALID_PROJECT,
            "prompt": "test prompt",
            "createdAt": "2026-01-01T00:00:00+00:00",
            "events": [],
        }
        _save_run(run)
        loaded = _load_run(run["id"])
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["id"], run["id"])
        self.assertEqual(loaded["status"], "pending")
        (RUNS_DIR / f"{run['id']}.json").unlink(missing_ok=True)

    def test_load_run_not_found(self) -> None:
        self.assertIsNone(_load_run("nonexistent_id_1234"))

    def test_load_run_rejects_traversal(self) -> None:
        self.assertIsNone(_load_run("../etc/passwd"))
        self.assertIsNone(_load_run("foo/bar"))


class BuildAgentCmdTests(unittest.TestCase):
    """Unit tests for _build_agent_cmd argv builders."""

    def _cwd(self) -> Path:
        return Path("/tmp/project")

    # ---- OpenCode ----

    def test_opencode_default_model(self) -> None:
        cmd, stdin = _build_agent_cmd("opencode", "default", "default", self._cwd())
        self.assertFalse(stdin)
        self.assertIn("opencode", cmd[0])
        self.assertNotIn("--model", cmd)

    def test_opencode_explicit_model(self) -> None:
        cmd, stdin = _build_agent_cmd("opencode", "my-model", "default", self._cwd())
        self.assertFalse(stdin)
        self.assertIn("--model", cmd)
        idx = cmd.index("--model")
        self.assertEqual(cmd[idx + 1], "my-model")

    def test_opencode_prompt_in_argv(self) -> None:
        """OpenCode puts prompt in argv."""
        cmd, stdin = _build_agent_cmd("opencode", "default", "default", self._cwd())
        # The prompt is appended by the caller, not by build_cmd
        self.assertFalse(stdin)

    # ---- Claude ----

    def test_claude_default_model(self) -> None:
        cmd, stdin = _build_agent_cmd("claude", "default", "default", self._cwd())
        self.assertTrue(stdin)
        self.assertIn("claude", cmd[0])
        self.assertIn("-p", cmd)
        self.assertIn("--output-format", cmd)
        self.assertIn("stream-json", cmd)
        self.assertIn("--verbose", cmd)
        self.assertIn("--permission-mode", cmd)
        self.assertIn("bypassPermissions", cmd)
        self.assertNotIn("--model", cmd)

    def test_claude_explicit_model(self) -> None:
        cmd, stdin = _build_agent_cmd("claude", "sonnet", "default", self._cwd())
        self.assertTrue(stdin)
        self.assertIn("--model", cmd)
        idx = cmd.index("--model")
        self.assertEqual(cmd[idx + 1], "sonnet")

    def test_claude_prompt_via_stdin(self) -> None:
        """Claude uses stdin, not argv, for prompt."""
        _, stdin = _build_agent_cmd("claude", "default", "default", self._cwd())
        self.assertTrue(stdin)

    # ---- Codex ----

    def test_codex_default_model(self) -> None:
        cmd, stdin = _build_agent_cmd("codex", "default", "default", self._cwd())
        self.assertTrue(stdin)
        self.assertIn("codex", cmd[0])
        self.assertIn("exec", cmd)
        self.assertIn("--json", cmd)
        self.assertIn("--skip-git-repo-check", cmd)
        self.assertIn("--sandbox", cmd)
        self.assertIn("workspace-write", cmd)
        self.assertNotIn("--model", cmd)

    def test_codex_explicit_model(self) -> None:
        cmd, stdin = _build_agent_cmd("codex", "gpt-5.4", "default", self._cwd())
        self.assertTrue(stdin)
        self.assertIn("--model", cmd)
        idx = cmd.index("--model")
        self.assertEqual(cmd[idx + 1], "gpt-5.4")

    def test_codex_reasoning_in_argv(self) -> None:
        cmd, _ = _build_agent_cmd("codex", "default", "high", self._cwd())
        c_args = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-c" and i + 1 < len(cmd)]
        self.assertTrue(any("model_reasoning_effort=high" in a for a in c_args))

    def test_codex_default_reasoning_omitted(self) -> None:
        cmd, _ = _build_agent_cmd("codex", "default", "default", self._cwd())
        c_args = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-c" and i + 1 < len(cmd)]
        self.assertFalse(any("model_reasoning_effort" in a for a in c_args))

    def test_codex_cwd_in_argv(self) -> None:
        cwd = Path("/my/project")
        cmd, _ = _build_agent_cmd("codex", "default", "default", cwd)
        self.assertIn("-C", cmd)
        idx = cmd.index("-C")
        self.assertEqual(cmd[idx + 1], str(cwd))

    def test_codex_prompt_via_stdin(self) -> None:
        _, stdin = _build_agent_cmd("codex", "default", "default", self._cwd())
        self.assertTrue(stdin)

    # ---- Unknown agent ----

    def test_unknown_agent_raises(self) -> None:
        with self.assertRaises(ValueError):
            _build_agent_cmd("unknown", "default", "default", self._cwd())


class FileChangeTrackingTests(unittest.TestCase):
    """Unit tests for _snapshot_project and _compute_file_changes."""

    def _make_project(self, tmpdir: Path, files: dict[str, bytes]) -> Path:
        """Create a fake project directory with the given files."""
        for relpath, content in files.items():
            fpath = tmpdir / relpath
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_bytes(content)
        return tmpdir

    def test_snapshot_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            snap = _snapshot_project(Path(td))
            self.assertEqual(snap, {})

    def test_snapshot_captures_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self._make_project(p, {
                "spec/figure.yaml": b"figure:",
                "src/render.py": b"print()",
            })
            snap = _snapshot_project(p)
            self.assertIn("spec/figure.yaml", snap)
            self.assertIn("src/render.py", snap)
            self.assertEqual(len(snap), 2)

    def test_snapshot_ignores_pycache(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self._make_project(p, {
                "spec/figure.yaml": b"ok",
                "__pycache__/mod.cached": b"junk",
                "src/__pycache__/foo.pyc": b"junk",
            })
            snap = _snapshot_project(p)
            self.assertIn("spec/figure.yaml", snap)
            self.assertNotIn("__pycache__/mod.cached", snap)
            self.assertNotIn("src/__pycache__/foo.pyc", snap)

    def test_snapshot_ignores_ds_store(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self._make_project(p, {
                "spec/figure.yaml": b"ok",
                ".DS_Store": b"junk",
                "src/.DS_Store": b"junk",
            })
            snap = _snapshot_project(p)
            self.assertNotIn(".DS_Store", snap)
            self.assertNotIn("src/.DS_Store", snap)

    def test_snapshot_ignores_output_tmp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self._make_project(p, {
                "spec/figure.yaml": b"ok",
                "outputs/figure.tmp": b"temp",
                "outputs/result.png": b"png",
            })
            snap = _snapshot_project(p)
            self.assertNotIn("outputs/figure.tmp", snap)
            self.assertIn("outputs/result.png", snap)

    def test_snapshot_ignores_history_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self._make_project(p, {
                "spec/figure.yaml": b"ok",
                "history/old_version.yaml": b"old",
            })
            snap = _snapshot_project(p)
            self.assertNotIn("history/old_version.yaml", snap)

    def test_compute_added(self) -> None:
        before = {"a.txt": (10, 100, "aaa")}
        after = {"a.txt": (10, 100, "aaa"), "b.txt": (20, 200, "bbb")}
        changes = _compute_file_changes(before, after)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["path"], "b.txt")
        self.assertEqual(changes[0]["status"], "added")

    def test_compute_deleted(self) -> None:
        before = {"a.txt": (10, 100, "aaa"), "b.txt": (20, 200, "bbb")}
        after = {"a.txt": (10, 100, "aaa")}
        changes = _compute_file_changes(before, after)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["path"], "b.txt")
        self.assertEqual(changes[0]["status"], "deleted")

    def test_compute_modified(self) -> None:
        before = {"a.txt": (10, 100, "aaa")}
        after = {"a.txt": (15, 200, "ccc")}
        changes = _compute_file_changes(before, after)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["path"], "a.txt")
        self.assertEqual(changes[0]["status"], "modified")

    def test_compute_no_changes(self) -> None:
        before = {"a.txt": (10, 100, "aaa")}
        after = {"a.txt": (10, 100, "aaa")}
        changes = _compute_file_changes(before, after)
        self.assertEqual(changes, [])

    def test_compute_mixed_changes(self) -> None:
        before = {"a.txt": (10, 100, "aaa"), "c.txt": (30, 300, "ccc")}
        after = {"a.txt": (10, 100, "aaa"), "b.txt": (20, 200, "bbb"), "c.txt": (35, 400, "ddd")}
        changes = _compute_file_changes(before, after)
        paths = {c["path"]: c["status"] for c in changes}
        self.assertEqual(paths.get("a.txt"), None)  # unchanged
        self.assertEqual(paths.get("b.txt"), "added")
        self.assertEqual(paths.get("c.txt"), "modified")

    def test_snapshot_fingerprint_stability(self) -> None:
        """Same file content should produce same fingerprint."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "a.txt").write_text("hello")
            snap1 = _snapshot_project(p)
            snap2 = _snapshot_project(p)
            self.assertEqual(snap1["a.txt"], snap2["a.txt"])


class AgentRunFileChangesTests(unittest.TestCase):
    """Integration tests for file change tracking in agent runs."""

    server: HTTPServer
    port: int
    thread: Thread

    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _free_port()
        cls.server = HTTPServer(("127.0.0.1", cls.port), _QuietHandler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _post_json(self, path: str, data: dict) -> tuple[int, dict]:
        body = json.dumps(data).encode()
        req = Request(self._url(path), data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except Exception as e:
            if hasattr(e, "code") and hasattr(e, "read"):
                return e.code, json.loads(e.read())
            raise

    def _get_json(self, path: str) -> tuple[int, dict]:
        req = Request(self._url(path), method="GET")
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except Exception as e:
            if hasattr(e, "code") and hasattr(e, "read"):
                return e.code, json.loads(e.read())
            raise

    def _wait_for_status(self, run_id: str, timeout: float = 10.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            _, data = self._get_json(f"/api/agent-runs/{run_id}")
            if data.get("status") not in ("pending", "running"):
                return data
            time.sleep(0.05)
        self.fail(f"Run {run_id} did not complete within {timeout}s")
        return {}

    def _cleanup_run(self, run_id: str) -> None:
        (RUNS_DIR / f"{run_id}.json").unlink(missing_ok=True)

    @patch("api.server.subprocess.Popen")
    def test_run_record_has_file_changes_field(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen(returncode=0)
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "test",
        })
        self.assertIn("fileChanges", created)
        self.assertEqual(created["fileChanges"], [])
        final = self._wait_for_status(created["id"])
        self.assertIn("fileChanges", final)
        self.assertIsInstance(final["fileChanges"], list)
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    @patch("api.server._snapshot_project")
    def test_file_changes_recorded_on_completion(self, mock_snapshot: MagicMock, mock_popen: MagicMock) -> None:
        """Mock snapshots to simulate file changes."""
        mock_popen.return_value = _make_mock_popen(returncode=0)
        # Before: only figure.yaml; After: figure.yaml modified + new file
        mock_snapshot.side_effect = [
            {"spec/figure.yaml": (100, 1000, "aaa")},  # before
            {"spec/figure.yaml": (150, 2000, "bbb"), "outputs/new.png": (500, 3000, "ccc")},  # after
        ]
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "do work",
        })
        final = self._wait_for_status(created["id"])
        self.assertEqual(final["status"], "completed")
        changes = final["fileChanges"]
        self.assertEqual(len(changes), 2)
        paths = {c["path"]: c["status"] for c in changes}
        self.assertEqual(paths["spec/figure.yaml"], "modified")
        self.assertEqual(paths["outputs/new.png"], "added")

        # Check event was added
        change_events = [e for e in final["events"] if e["type"] == "file_changes"]
        self.assertGreater(len(change_events), 0)
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    @patch("api.server._snapshot_project")
    def test_file_changes_empty_when_no_changes(self, mock_snapshot: MagicMock, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen(returncode=0)
        snap = {"spec/figure.yaml": (100, 1000, "aaa")}
        mock_snapshot.side_effect = [snap, snap]  # identical before/after
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "no change",
        })
        final = self._wait_for_status(created["id"])
        self.assertEqual(final["fileChanges"], [])
        # No file_changes event should be present
        change_events = [e for e in final["events"] if e["type"] == "file_changes"]
        self.assertEqual(len(change_events), 0)
        self._cleanup_run(created["id"])


class AsyncAgentRunTests(unittest.TestCase):
    """Tests for the async POST /api/agent-runs + GET events + cancel."""

    server: HTTPServer
    port: int
    thread: Thread

    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _free_port()
        cls.server = HTTPServer(("127.0.0.1", cls.port), _QuietHandler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _post_json(self, path: str, data: dict) -> tuple[int, dict]:
        body = json.dumps(data).encode()
        req = Request(self._url(path), data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except Exception as e:
            if hasattr(e, "code") and hasattr(e, "read"):
                return e.code, json.loads(e.read())
            raise

    def _get_json(self, path: str) -> tuple[int, dict]:
        req = Request(self._url(path), method="GET")
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except Exception as e:
            if hasattr(e, "code") and hasattr(e, "read"):
                return e.code, json.loads(e.read())
            raise

    def _get_text(self, path: str) -> tuple[int, str]:
        req = Request(self._url(path), method="GET")
        try:
            with urlopen(req) as resp:
                return resp.status, resp.read().decode("utf-8")
        except Exception as e:
            if hasattr(e, "code") and hasattr(e, "read"):
                return e.code, e.read().decode("utf-8")
            raise

    def _cleanup_run(self, run_id: str) -> None:
        (RUNS_DIR / f"{run_id}.json").unlink(missing_ok=True)

    def _wait_for_status(self, run_id: str, timeout: float = 10.0) -> dict:
        """Poll until run leaves 'pending'/'running' status."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            _, data = self._get_json(f"/api/agent-runs/{run_id}")
            if data.get("status") not in ("pending", "running"):
                return data
            time.sleep(0.05)
        self.fail(f"Run {run_id} did not complete within {timeout}s (status={data.get('status')})")
        return {}  # unreachable

    # ---- Validation tests (no mock needed) ----

    def test_empty_prompt_rejected(self) -> None:
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "",
        })
        self.assertEqual(status, 400)
        self.assertIn("empty", data["error"].lower())

    def test_whitespace_only_prompt_rejected(self) -> None:
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "   \n\t  ",
        })
        self.assertEqual(status, 400)
        self.assertIn("empty", data["error"].lower())

    def test_invalid_project_rejected(self) -> None:
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": "nonexistent_xyz", "prompt": "test",
        })
        self.assertEqual(status, 400)
        self.assertIn("Invalid project", data["error"])

    def test_unsupported_agent_rejected(self) -> None:
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "gemini", "project": VALID_PROJECT, "prompt": "test",
        })
        self.assertEqual(status, 400)
        self.assertIn("not supported", data["error"].lower())

    # ---- Async run tests (mock Popen) ----

    @patch("api.server.subprocess.Popen")
    def test_post_returns_202_pending(self, mock_popen: MagicMock) -> None:
        # Use a blocking Popen so we can verify pending status before it completes
        block = threading.Event()
        mock_popen.return_value = _make_mock_popen(returncode=0, block_event=block)
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "model": "default", "project": VALID_PROJECT, "prompt": "hello",
        })
        self.assertEqual(status, 202)
        self.assertEqual(data["status"], "pending")
        self.assertIn("id", data)
        # Release the background thread
        block.set()
        time.sleep(0.3)
        self._cleanup_run(data["id"])

    @patch("api.server.subprocess.Popen")
    def test_run_completes_successfully(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen(stdout_lines=["line1", "line2"], returncode=0)
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "model": "default", "project": VALID_PROJECT, "prompt": "go",
        })
        run_id = created["id"]
        final = self._wait_for_status(run_id)
        self.assertEqual(final["status"], "completed")
        self.assertEqual(final["returncode"], 0)
        self.assertIn("line1", final["stdout"])
        self._cleanup_run(run_id)

    @patch("api.server.subprocess.Popen")
    def test_run_fails_with_nonzero_exit(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen(stderr_lines=["boom"], returncode=1)
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "fail",
        })
        final = self._wait_for_status(created["id"])
        self.assertEqual(final["status"], "failed")
        self.assertEqual(final["returncode"], 1)
        self.assertIn("boom", final["stderr"])
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    def test_default_model_not_in_command(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen()
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "model": "default", "project": VALID_PROJECT, "prompt": "hi",
        })
        self._wait_for_status(created["id"])
        run = _load_run(created["id"])
        self.assertNotIn("--model", run["command"])
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    def test_explicit_model_in_command(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen()
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "model": "opencode/minimax-m2.5-free",
            "project": VALID_PROJECT, "prompt": "hi",
        })
        self._wait_for_status(created["id"])
        run = _load_run(created["id"])
        self.assertIn("--model", run["command"])
        idx = run["command"].index("--model")
        self.assertEqual(run["command"][idx + 1], "opencode/minimax-m2.5-free")
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    def test_unknown_model_rejected(self, mock_popen: MagicMock) -> None:
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "model": "not-a-real-model",
            "project": VALID_PROJECT, "prompt": "hello",
        })
        self.assertEqual(status, 400)
        self.assertIn("Invalid model", data["error"])
        mock_popen.assert_not_called()

    @patch("api.server.subprocess.Popen")
    def test_boundary_appended_to_prompt(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen()
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "model": "default", "project": VALID_PROJECT, "prompt": "my request",
        })
        self._wait_for_status(created["id"])
        run = _load_run(created["id"])
        full_prompt = run["command"][-1]
        self.assertIn("BOUNDARIES", full_prompt)
        self.assertIn("my request", full_prompt)
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    def test_user_prompt_preserved_in_record(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen()
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "user says hi",
        })
        self._wait_for_status(created["id"])
        run = _load_run(created["id"])
        self.assertEqual(run["prompt"], "user says hi")
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    def test_events_written_for_stdout(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen(stdout_lines=["hello world", "second line"])
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "stream test",
        })
        final = self._wait_for_status(created["id"])
        event_types = [e["type"] for e in final["events"]]
        self.assertIn("stdout", event_types)
        stdout_events = [e for e in final["events"] if e["type"] == "stdout"]
        details = [e["detail"] for e in stdout_events]
        self.assertTrue(any("hello world" in d for d in details))
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    def test_events_written_for_stderr(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen(stderr_lines=["err output"], returncode=1)
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "err test",
        })
        final = self._wait_for_status(created["id"])
        stderr_events = [e for e in final["events"] if e["type"] == "stderr"]
        self.assertTrue(any("err output" in e["detail"] for e in stderr_events))
        self._cleanup_run(created["id"])

    # ---- Claude adapter tests ----

    @patch("api.server.subprocess.Popen")
    def test_claude_accepted_and_completes(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen(stdout_lines=["claude output"], returncode=0)
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "claude", "model": "default", "project": VALID_PROJECT, "prompt": "do stuff",
        })
        self.assertEqual(created["status"], "pending")
        final = self._wait_for_status(created["id"])
        self.assertEqual(final["status"], "completed")
        self.assertEqual(final["agentId"], "claude")
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    def test_claude_prompt_not_in_argv(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen()
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "claude", "project": VALID_PROJECT, "prompt": "secret prompt",
        })
        self._wait_for_status(created["id"])
        run = _load_run(created["id"])
        # Prompt must NOT appear in command argv (sent via stdin)
        for arg in run["command"]:
            self.assertNotIn("secret prompt", arg)
        # Verify adapter info
        self.assertTrue(run["adapter"]["promptViaStdin"])
        self.assertEqual(run["adapter"]["id"], "claude")
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    def test_claude_explicit_model_in_argv(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen()
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "claude", "model": "sonnet", "project": VALID_PROJECT, "prompt": "hi",
        })
        self._wait_for_status(created["id"])
        run = _load_run(created["id"])
        self.assertIn("--model", run["command"])
        idx = run["command"].index("--model")
        self.assertEqual(run["command"][idx + 1], "sonnet")
        self._cleanup_run(created["id"])

    # ---- Codex adapter tests ----

    @patch("api.server.subprocess.Popen")
    def test_codex_accepted_and_completes(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen(stdout_lines=["codex output"], returncode=0)
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "codex", "model": "default", "project": VALID_PROJECT, "prompt": "do stuff",
        })
        self.assertEqual(created["status"], "pending")
        final = self._wait_for_status(created["id"])
        self.assertEqual(final["status"], "completed")
        self.assertEqual(final["agentId"], "codex")
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    def test_codex_prompt_not_in_argv(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen()
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "codex", "project": VALID_PROJECT, "prompt": "secret prompt",
        })
        self._wait_for_status(created["id"])
        run = _load_run(created["id"])
        for arg in run["command"]:
            self.assertNotIn("secret prompt", arg)
        self.assertTrue(run["adapter"]["promptViaStdin"])
        self.assertEqual(run["adapter"]["id"], "codex")
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    def test_codex_reasoning_in_argv(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen()
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "codex", "model": "default", "reasoning": "high",
            "project": VALID_PROJECT, "prompt": "hi",
        })
        self._wait_for_status(created["id"])
        run = _load_run(created["id"])
        self.assertIn("-c", run["command"])
        # Find the reasoning effort arg
        c_args = [run["command"][i + 1] for i, a in enumerate(run["command"]) if a == "-c" and i + 1 < len(run["command"])]
        self.assertTrue(any("model_reasoning_effort=high" in a for a in c_args))
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    def test_codex_default_reasoning_not_in_argv(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen()
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "codex", "model": "default", "reasoning": "default",
            "project": VALID_PROJECT, "prompt": "hi",
        })
        self._wait_for_status(created["id"])
        run = _load_run(created["id"])
        # Should not have model_reasoning_effort when reasoning=default
        c_args = [run["command"][i + 1] for i, a in enumerate(run["command"]) if a == "-c" and i + 1 < len(run["command"])]
        self.assertFalse(any("model_reasoning_effort" in a for a in c_args))
        self._cleanup_run(created["id"])

    # ---- Model validation per agent ----

    @patch("api.server.subprocess.Popen")
    def test_opencode_model_rejected_for_claude(self, mock_popen: MagicMock) -> None:
        """OpenCode-specific model should be rejected when agentId=claude."""
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "claude", "model": "opencode/minimax-m2.5-free",
            "project": VALID_PROJECT, "prompt": "hello",
        })
        self.assertEqual(status, 400)
        self.assertIn("Invalid model", data["error"])
        mock_popen.assert_not_called()

    @patch("api.server.subprocess.Popen")
    def test_claude_model_rejected_for_codex(self, mock_popen: MagicMock) -> None:
        """Claude-specific model should be rejected when agentId=codex."""
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "codex", "model": "sonnet",
            "project": VALID_PROJECT, "prompt": "hello",
        })
        self.assertEqual(status, 400)
        self.assertIn("Invalid model", data["error"])
        mock_popen.assert_not_called()


class CancelRunTests(unittest.TestCase):
    """Tests for POST /api/agent-runs/<id>/cancel."""

    server: HTTPServer
    port: int
    thread: Thread

    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _free_port()
        cls.server = HTTPServer(("127.0.0.1", cls.port), _QuietHandler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _post_json(self, path: str, data: dict) -> tuple[int, dict]:
        body = json.dumps(data).encode()
        req = Request(self._url(path), data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except Exception as e:
            if hasattr(e, "code") and hasattr(e, "read"):
                return e.code, json.loads(e.read())
            raise

    def _get_json(self, path: str) -> tuple[int, dict]:
        req = Request(self._url(path), method="GET")
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except Exception as e:
            if hasattr(e, "code") and hasattr(e, "read"):
                return e.code, json.loads(e.read())
            raise

    def _wait_for_status(self, run_id: str, timeout: float = 10.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            _, data = self._get_json(f"/api/agent-runs/{run_id}")
            if data.get("status") not in ("pending", "running"):
                return data
            time.sleep(0.05)
        self.fail(f"Run {run_id} did not complete within {timeout}s")
        return {}

    def _cleanup_run(self, run_id: str) -> None:
        (RUNS_DIR / f"{run_id}.json").unlink(missing_ok=True)

    @patch("api.server.subprocess.Popen")
    def test_cancel_pending_run(self, mock_popen: MagicMock) -> None:
        """Cancel a run while the process is still running."""
        block = threading.Event()
        mock_popen.return_value = _make_mock_popen(returncode=1, stderr_lines=["err"], block_event=block)
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "render",
        })
        run_id = created["id"]

        # Wait until the run is actually "running" (not just "pending")
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            _, r = self._get_json(f"/api/agent-runs/{run_id}")
            if r.get("status") == "running":
                break
            time.sleep(0.05)
        else:
            self.fail("Run never entered 'running' status")

        # Now cancel — should work since process is still alive
        status, data = self._post_json(f"/api/agent-runs/{run_id}/cancel", {})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "cancelled")
        self.assertTrue(any(e["type"] == "cancelled" for e in data["events"]))

        # Release the mock process
        block.set()
        time.sleep(0.3)
        self._cleanup_run(run_id)

    @patch("api.server.subprocess.Popen")
    def test_cancel_already_completed_returns_409(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen(returncode=0)
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "test",
        })
        self._wait_for_status(created["id"])
        status, _ = self._post_json(f"/api/agent-runs/{created['id']}/cancel", {})
        self.assertEqual(status, 409)
        self._cleanup_run(created["id"])


class SSEEventStreamTests(unittest.TestCase):
    """Tests for GET /api/agent-runs/<id>/events SSE endpoint."""

    server: HTTPServer
    port: int
    thread: Thread

    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _free_port()
        cls.server = HTTPServer(("127.0.0.1", cls.port), _QuietHandler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _post_json(self, path: str, data: dict) -> tuple[int, dict]:
        body = json.dumps(data).encode()
        req = Request(self._url(path), data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except Exception as e:
            if hasattr(e, "code") and hasattr(e, "read"):
                return e.code, json.loads(e.read())
            raise

    def _get_text(self, path: str) -> tuple[int, str]:
        req = Request(self._url(path), method="GET")
        try:
            with urlopen(req) as resp:
                return resp.status, resp.read().decode("utf-8")
        except Exception as e:
            if hasattr(e, "code") and hasattr(e, "read"):
                return e.code, e.read().decode("utf-8")
            raise

    def _get_json(self, path: str) -> tuple[int, dict]:
        req = Request(self._url(path), method="GET")
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except Exception as e:
            if hasattr(e, "code") and hasattr(e, "read"):
                return e.code, json.loads(e.read())
            raise

    def _wait_for_status(self, run_id: str, timeout: float = 10.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            _, data = self._get_json(f"/api/agent-runs/{run_id}")
            if data.get("status") not in ("pending", "running"):
                return data
            time.sleep(0.05)
        self.fail(f"Run {run_id} did not complete within {timeout}s")
        return {}

    def _cleanup_run(self, run_id: str) -> None:
        (RUNS_DIR / f"{run_id}.json").unlink(missing_ok=True)

    @patch("api.server.subprocess.Popen")
    def test_sse_returns_valid_text_event_stream(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen(stdout_lines=["output line"], returncode=0)
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "sse test",
        })
        self._wait_for_status(created["id"])

        status, body = self._get_text(f"/api/agent-runs/{created['id']}/events")
        self.assertEqual(status, 200)
        # SSE format: lines starting with "id:", "event:", "data:"
        self.assertIn("event:", body)
        self.assertIn("data:", body)
        self.assertIn("id:", body)
        self._cleanup_run(created["id"])

    @patch("api.server.subprocess.Popen")
    def test_sse_after_parameter_filters_events(self, mock_popen: MagicMock) -> None:
        mock_popen.return_value = _make_mock_popen(stdout_lines=["first", "second"], returncode=0)
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode", "project": VALID_PROJECT, "prompt": "filter test",
        })
        self._wait_for_status(created["id"])

        # Get all events to find a valid event ID
        run = _load_run(created["id"])
        all_events = run["events"]
        self.assertGreater(len(all_events), 1)

        # Use the ID of the first event to filter
        first_event_id = all_events[0]["id"]
        status, body = self._get_text(f"/api/agent-runs/{created['id']}/events?after={first_event_id}")
        self.assertEqual(status, 200)

        # Should not contain the first event's data
        first_data = json.dumps(all_events[0])
        self.assertNotIn(first_data, body)

        # Should contain later events
        if len(all_events) > 1:
            later_data = json.dumps(all_events[-1])
            self.assertIn(later_data, body)
        self._cleanup_run(created["id"])

    def test_sse_nonexistent_run_returns_404(self) -> None:
        status, body = self._get_text("/api/agent-runs/nonexistent_1234/events")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
