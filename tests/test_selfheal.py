import tempfile
import unittest
from pathlib import Path

from agentops.selfheal.patterns import PatternRegistry, MAX_REPAIR_ATTEMPTS
from agentops.config import Settings
from agentops.controller import Controller
from agentops.store import Store
from agentops.selfheal.maintenance import MaintenanceLoop
from tests.fakes import *


class SelfHealPatternTests(unittest.TestCase):
    def test_classifies_terminal_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = PatternRegistry(path=str(Path(tmp) / "p.json"))
            self.assertEqual(reg.classify("Cursor terminal/unknown status: ERROR"), "worker_terminal_error")

    def test_caps_repair_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = PatternRegistry(path=str(Path(tmp) / "p.json"))
            for _ in range(MAX_REPAIR_ATTEMPTS):
                reg.record_attempt("worker_terminal_error", success=False, detail="ERROR")
            self.assertTrue(reg.is_blocked("worker_terminal_error"))


class SelfHealAttemptCapIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings(
            REPO, "fake-gh", "fake-cursor", "1:fake", 42, frozenset({42}),
            state_path=":memory:", allow_runs=True, spend_limit_confirmed=True,
            protection_confirmed=True, autonomous_default=False, auto_merge_safe=False,
            max_attempts=2, max_stuck_retries=3, stuck_backoff_seconds=5,
        )
        self.db = Store(":memory:")
        self.gh, self.cu, self.tg = FakeGitHub(), FakeCursor(), FakeTelegram()
        self.clock = Clock()
        self.c = Controller(self.cfg, self.db, self.gh, self.cu, self.tg, backlog(), clock=self.clock)

    def test_retryable_attempt_cap_triggers_stuck_recovery(self):
        self.c.handle(update("/resume"))
        self.c.tick()
        t = self.db.task("T001")
        t.update(
            state="BLOCKED",
            retryable=True,
            attempt=2,
            feedback="Cursor terminal/unknown status: ERROR",
            role="dev",
            base_sha=BASE,
        )
        self.db.save(t)
        self.c.tick()
        t = self.db.task("T001")
        self.assertIn(t["state"], {"LAUNCHING_DEV", "DEVELOPING"})
        self.assertGreaterEqual(int(t.get("stuck_retries", 0)), 1)

    def test_maintenance_loop_writes_report(self):
        self.c.handle(update("/resume"))
        self.c.tick()
        t = self.db.task("T001")
        t.update(
            state="BLOCKED",
            retryable=True,
            attempt=2,
            feedback="Cursor terminal/unknown status: ERROR",
            role="dev",
            base_sha=BASE,
        )
        self.db.save(t)
        with tempfile.TemporaryDirectory() as tmp:
            import agentops.selfheal.maintenance as maint
            old = maint.default_report_dir
            maint.default_report_dir = lambda: Path(tmp)
            try:
                loop = MaintenanceLoop(self.cfg, self.db, self.c, Path(__file__).resolve().parents[1])
                loop.registry = PatternRegistry(path=str(Path(tmp) / "patterns.json"))
                reports = loop.tick()
            finally:
                maint.default_report_dir = old
        self.assertTrue(reports)
        self.assertIn(reports[0]["status"], {"HEALED", "REPAIR_ATTEMPTED", "SELF_HEAL_BLOCKED"})
        self.assertTrue(reports[0].get("report_path"))
