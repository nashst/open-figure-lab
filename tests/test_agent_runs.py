"""Tests for the agent-run API helpers and HTTP handlers."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from http.server import HTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.request import Request, urlopen

# Ensure the app package is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from api.server import (  # noqa: E402
    RUNS_DIR,
    _generate_run_id,
    _is_valid_project,
    _load_run,
    _save_run,
    APIHandler,
)

VALID_PROJECT = "soc_proxy_fig2"


def _free_port() -> int:
    """Return an available localhost port."""
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _mock_completed_process(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    """Build a fake CompletedProcess for mocking."""
    return subprocess.CompletedProcess(
        args=["opencode", "run", "..."],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


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


class AgentRunAPITests(unittest.TestCase):
    """Integration tests for /api/agent-runs endpoints over HTTP."""

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

    # ---- helpers ----

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

    def _cleanup_run(self, run_id: str) -> None:
        (RUNS_DIR / f"{run_id}.json").unlink(missing_ok=True)

    # ---- validation tests (no mock needed) ----

    def test_empty_prompt_rejected(self) -> None:
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "project": VALID_PROJECT,
            "prompt": "",
        })
        self.assertEqual(status, 400)
        self.assertIn("empty", data["error"].lower())

    def test_whitespace_only_prompt_rejected(self) -> None:
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "project": VALID_PROJECT,
            "prompt": "   \n\t  ",
        })
        self.assertEqual(status, 400)
        self.assertIn("empty", data["error"].lower())

    def test_invalid_project_rejected(self) -> None:
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "project": "nonexistent_xyz",
            "prompt": "test",
        })
        self.assertEqual(status, 400)
        self.assertIn("Invalid project", data["error"])

    def test_non_opencode_agent_rejected(self) -> None:
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "claude",
            "project": VALID_PROJECT,
            "prompt": "test",
        })
        self.assertEqual(status, 400)
        self.assertIn("not implemented", data["error"].lower())

    # ---- mock subprocess tests ----

    @patch("api.server.subprocess.run")
    def test_opencode_success(self, mock_run: unittest.mock.MagicMock) -> None:
        mock_run.return_value = _mock_completed_process(returncode=0, stdout="done", stderr="")
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "model": "default",
            "project": VALID_PROJECT,
            "prompt": "validate the figure",
        })
        self.assertEqual(status, 201)
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["returncode"], 0)
        self.assertIn("command", data)
        self.assertIsNotNone(data["startedAt"])
        self.assertIsNotNone(data["completedAt"])
        self._cleanup_run(data["id"])

    @patch("api.server.subprocess.run")
    def test_opencode_failure(self, mock_run: unittest.mock.MagicMock) -> None:
        mock_run.return_value = _mock_completed_process(returncode=1, stdout="", stderr="something broke")
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "model": "default",
            "project": VALID_PROJECT,
            "prompt": "do a thing",
        })
        self.assertEqual(status, 201)
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["returncode"], 1)
        self.assertIn("something broke", data["stderr"])
        self._cleanup_run(data["id"])

    @patch("api.server.subprocess.run")
    def test_default_model_not_in_command(self, mock_run: unittest.mock.MagicMock) -> None:
        mock_run.return_value = _mock_completed_process()
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "model": "default",
            "project": VALID_PROJECT,
            "prompt": "hello",
        })
        self.assertEqual(status, 201)
        cmd = data["command"]
        self.assertIn("opencode", cmd[0])
        self.assertNotIn("--model", cmd)
        self._cleanup_run(data["id"])

    @patch("api.server.subprocess.run")
    def test_explicit_model_in_command(self, mock_run: unittest.mock.MagicMock) -> None:
        mock_run.return_value = _mock_completed_process()
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "model": "opencode/minimax-m2.5-free",
            "project": VALID_PROJECT,
            "prompt": "hello",
        })
        self.assertEqual(status, 201)
        cmd = data["command"]
        self.assertIn("--model", cmd)
        model_idx = cmd.index("--model")
        self.assertEqual(cmd[model_idx + 1], "opencode/minimax-m2.5-free")
        self._cleanup_run(data["id"])

    @patch("api.server.subprocess.run")
    def test_unknown_model_rejected(self, mock_run: unittest.mock.MagicMock) -> None:
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "model": "not-a-real-model",
            "project": VALID_PROJECT,
            "prompt": "hello",
        })
        self.assertEqual(status, 400)
        self.assertIn("Invalid model", data["error"])
        mock_run.assert_not_called()

    @patch("api.server.subprocess.run")
    def test_boundary_appended_to_prompt(self, mock_run: unittest.mock.MagicMock) -> None:
        mock_run.return_value = _mock_completed_process()
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "model": "default",
            "project": VALID_PROJECT,
            "prompt": "my request",
        })
        self.assertEqual(status, 201)
        # The last element of the command is the full prompt
        cmd = data["command"]
        full_prompt = cmd[-1]
        self.assertIn("BOUNDARIES", full_prompt)
        self.assertIn("my request", full_prompt)
        self.assertTrue(full_prompt.index("BOUNDARIES") < full_prompt.index("my request"))
        self._cleanup_run(data["id"])

    @patch("api.server.subprocess.run")
    def test_prompt_saved_in_run_record(self, mock_run: unittest.mock.MagicMock) -> None:
        """Verify the original user prompt (not the boundary-augmented one) is stored."""
        mock_run.return_value = _mock_completed_process()
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "model": "default",
            "project": VALID_PROJECT,
            "prompt": "user says hi",
        })
        self.assertEqual(status, 201)
        # run.prompt should be the original, not the boundary-wrapped version
        self.assertEqual(data["prompt"], "user says hi")
        self._cleanup_run(data["id"])


class CancelRunTests(unittest.TestCase):
    """Tests for cancel endpoint (unchanged behaviour)."""

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

    @patch("api.server.subprocess.run")
    def test_cancel_run(self, mock_run: unittest.mock.MagicMock) -> None:
        # Use a failed run so status is "failed" (cancellable, unlike "completed")
        mock_run.return_value = _mock_completed_process(returncode=1, stderr="err")
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "project": VALID_PROJECT,
            "prompt": "render",
        })
        run_id = created["id"]
        self.assertEqual(created["status"], "failed")

        status, data = self._post_json(f"/api/agent-runs/{run_id}/cancel", {})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "cancelled")
        self.assertTrue(any(e["type"] == "cancelled" for e in data["events"]))
        (RUNS_DIR / f"{run_id}.json").unlink(missing_ok=True)

    @patch("api.server.subprocess.run")
    def test_cancel_already_completed_returns_409(self, mock_run: unittest.mock.MagicMock) -> None:
        mock_run.return_value = _mock_completed_process(returncode=0)
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "project": VALID_PROJECT,
            "prompt": "test",
        })
        run_id = created["id"]
        self.assertEqual(created["status"], "completed")

        status, data = self._post_json(f"/api/agent-runs/{run_id}/cancel", {})
        self.assertEqual(status, 409)
        (RUNS_DIR / f"{run_id}.json").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
