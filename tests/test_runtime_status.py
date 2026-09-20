import tempfile
import unittest
from pathlib import Path

from agentops.config import Settings
from agentops.runtime_status import build_runtime_config, build_status, write_runtime_config, write_status
from agentops.store import Store
from tests.fakes import REPO


class RuntimeStatusTests(unittest.TestCase):
    def test_idle_when_unpaused_and_no_work(self):
        db = Store(":memory:")
        db.set("paused", False)
        db.save({"id": "T001", "state": "PENDING", "attempt": 0})
        payload = build_status(db, pid=9, process_alive=True, auto_merge_safe=True, now=100.0)
        self.assertEqual(payload["status"], "IDLE")
        self.assertEqual(payload["next_queued_task"], "T001")
        self.assertTrue(payload["process_alive"])

    def test_stopped_when_process_dead(self):
        db = Store(":memory:")
        db.set("paused", False)
        db.save({"id": "T001", "state": "DEVELOPING", "attempt": 1, "role": "dev"})
        payload = build_status(db, pid=9, process_alive=False, auto_merge_safe=True, now=100.0)
        self.assertEqual(payload["status"], "STOPPED")
        self.assertIsNone(payload["current_agent"])

    def test_running_claims_agent_only_when_alive(self):
        db = Store(":memory:")
        db.set("paused", False)
        db.save({"id": "T001", "state": "DEVELOPING", "attempt": 1, "role": "dev"})
        payload = build_status(db, pid=9, process_alive=True, auto_merge_safe=True, now=100.0)
        self.assertEqual(payload["status"], "RUNNING")
        self.assertEqual(payload["current_agent"], "Kian")

    def test_blocked_on_waiting_approval(self):
        db = Store(":memory:")
        db.set("paused", False)
        db.save({"id": "T001", "state": "WAITING_APPROVAL", "attempt": 1, "approval_reasons": ["protected path"]})
        payload = build_status(db, pid=9, process_alive=True, auto_merge_safe=True, now=100.0)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertIn("Human approval", payload["blocker_reason"])

    def test_atomic_write(self):
        db = Store(":memory:")
        db.set("paused", True)
        payload = build_status(db, pid=1, process_alive=True, auto_merge_safe=True, now=1.0)
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "runtime_status.json")
            write_status(path, payload)
            self.assertTrue(Path(path).is_file())
            text = Path(path).read_text(encoding="utf-8")
            self.assertIn('"status"', text)

    def test_runtime_config_has_no_secret_fields(self):
        cfg = Settings(
            REPO, "fake-gh-token", "fake-cursor", "1:fake", 42, frozenset({42}),
            allow_runs=True, spend_limit_confirmed=True, protection_confirmed=True,
            auto_merge_safe=True, autonomous_default=True, telegram_optional=True,
            agent_runtime="local",
        )
        payload = build_runtime_config(cfg)
        raw = str(payload)
        self.assertNotIn("fake-gh-token", raw)
        self.assertNotIn("fake-cursor", raw)
        self.assertNotIn("1:fake", raw)
        self.assertFalse(payload["monitoring_policy"]["read_secrets_env"])
        self.assertTrue(payload["monitoring_policy"]["read_only_commands_ok"])
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "runtime_config.json")
            write_runtime_config(path, payload)
            self.assertTrue(Path(path).is_file())
