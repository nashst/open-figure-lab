"""Tests for the agent-run API helpers and HTTP handlers."""

from __future__ import annotations

import json
import sys
import unittest
from http.server import HTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen

# Ensure the app package is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from api.server import (
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

        # cleanup
        (RUNS_DIR / f"{run['id']}.json").unlink(missing_ok=True)

    def test_load_run_not_found(self) -> None:
        self.assertIsNone(_load_run("nonexistent_id_1234"))

    def test_load_run_rejects_traversal(self) -> None:
        self.assertIsNone(_load_run("../etc/passwd"))
        self.assertIsNone(_load_run("foo/bar"))


class AgentRunAPITests(unittest.TestCase):
    """Integration tests for /api/agent-runs endpoints over HTTP."""

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

    def test_create_run(self) -> None:
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "model": "default",
            "reasoning": "default",
            "project": VALID_PROJECT,
            "prompt": "validate the figure",
        })
        self.assertEqual(status, 201)
        self.assertIn("id", data)
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["project"], VALID_PROJECT)
        self.assertEqual(data["prompt"], "validate the figure")
        self.assertIsInstance(data["events"], list)
        self.assertGreater(len(data["events"]), 0)

        # cleanup
        (RUNS_DIR / f"{data['id']}.json").unlink(missing_ok=True)

    def test_create_run_rejects_invalid_project(self) -> None:
        status, data = self._post_json("/api/agent-runs", {
            "agentId": "opencode",
            "project": "nonexistent_xyz",
            "prompt": "test",
        })
        self.assertEqual(status, 400)
        self.assertIn("error", data)

    def test_get_run(self) -> None:
        # Create first
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "claude",
            "model": "sonnet",
            "project": VALID_PROJECT,
            "prompt": "hello",
        })
        run_id = created["id"]

        status, data = self._get_json(f"/api/agent-runs/{run_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["id"], run_id)
        self.assertEqual(data["agentId"], "claude")

        # cleanup
        (RUNS_DIR / f"{run_id}.json").unlink(missing_ok=True)

    def test_get_run_not_found(self) -> None:
        status, data = self._get_json("/api/agent-runs/nonexistent_1234")
        self.assertEqual(status, 404)

    def test_cancel_run(self) -> None:
        # Create first
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "codex",
            "project": VALID_PROJECT,
            "prompt": "render",
        })
        run_id = created["id"]

        status, data = self._post_json(f"/api/agent-runs/{run_id}/cancel", {})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "cancelled")
        self.assertTrue(any(e["type"] == "cancelled" for e in data["events"]))

        # cleanup
        (RUNS_DIR / f"{run_id}.json").unlink(missing_ok=True)

    def test_cancel_already_cancelled(self) -> None:
        _, created = self._post_json("/api/agent-runs", {
            "agentId": "codex",
            "project": VALID_PROJECT,
            "prompt": "test",
        })
        run_id = created["id"]

        # First cancel
        self._post_json(f"/api/agent-runs/{run_id}/cancel", {})
        # Second cancel should 409
        status, data = self._post_json(f"/api/agent-runs/{run_id}/cancel", {})
        self.assertEqual(status, 409)

        # cleanup
        (RUNS_DIR / f"{run_id}.json").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
