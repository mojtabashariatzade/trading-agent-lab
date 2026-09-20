"""Regression: launch stalls must not freeze the queue after a fake heal."""
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from agentops.config import Settings
from agentops.controller import Controller
from agentops.selfheal.maintenance import MaintenanceLoop
from agentops.selfheal.patterns import MAX_REPAIR_ATTEMPTS, PatternRegistry
from agentops.store import Store
from tests.fakes import *


class LaunchQuotaAndStallTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings(
            REPO, "fake-gh", "fake-cursor", "1:fake", 42, frozenset({42}),
            state_path=":memory:", allow_runs=True, spend_limit_confirmed=True,
            protection_confirmed=True, autonomous_default=False, auto_merge_safe=False,
            max_attempts=2, max_stuck_retries=3, stuck_backoff_seconds=5,
            stuck_timeout_seconds=300, max_daily_launches=4,
        )
        self.db = Store(":memory:")
        self.gh, self.cu, self.tg = FakeGitHub(), FakeCursor(), FakeTelegram()
        self.clock = Clock()
        self.c = Controller(self.cfg, self.db, self.gh, self.cu, self.tg, backlog(), clock=self.clock)

    def test_stuck_restart_reuses_daily_quota(self):
        self.c.handle(update("/resume"))
        self.c.tick()
        self.assertEqual(self.db.launch_count(self.c.day()), 1)
        t = self.db.task("T001")
        t["last_progress_at"] = self.clock.now - 301
        t["backoff_until"] = 0
        self.db.save(t)
        self.c.cfg = replace(self.cfg, stuck_timeout_seconds=300, max_stuck_retries=3, stuck_backoff_seconds=5)
        self.c.tick()
        self.clock.now += 6
        self.c.tick()
        self.assertEqual(self.db.launch_count(self.c.day()), 1)
        self.assertGreaterEqual(len(self.cu.created), 2)

    def test_launching_without_run_id_recovers_in_90s(self):
        self.c.handle(update("/resume"))
        self.c.tick()
        t = self.db.task("T001")
        t.update(
            state="LAUNCHING_DEV",
            run_id=None,
            last_progress_at=self.clock.now - 91,
            backoff_until=0,
            progress_fingerprint="stale-launch",
        )
        self.db.save(t)
        before = int(t.get("stuck_retries", 0))
        self.c.tick()
        t = self.db.task("T001")
        self.assertGreaterEqual(int(t.get("stuck_retries", 0)), before + 1)

    def test_daily_limit_is_not_treated_as_stuck(self):
        for i in range(self.cfg.max_daily_launches):
            self.assertTrue(self.db.reserve(f"fill-{i}", self.c.day(), self.cfg.max_daily_launches))
        self.c.handle(update("/resume"))
        t = self.db.task("T001")
        t.update(
            state="LAUNCHING_DEV",
            role="dev",
            attempt=1,
            base_sha=BASE,
            run_id=None,
            last_progress_at=self.clock.now - 91,
            backoff_until=0,
            progress_fingerprint="daily_limit:x",
            stuck_retries=0,
        )
        self.db.save(t)
        self.c.tick()
        t = self.db.task("T001")
        self.assertEqual(int(t.get("stuck_retries", 0)), 0)
        self.assertTrue(str(t.get("progress_fingerprint") or "").startswith("daily_limit:"))


class SelfHealNoDeadlockTests(unittest.TestCase):
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
        self.c.handle(update("/resume"))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.loop = MaintenanceLoop(self.cfg, self.db, self.c, Path(__file__).resolve().parents[2])
        self.loop.report_dir = Path(self.tmp.name)
        self.loop.registry = PatternRegistry(path=str(Path(self.tmp.name) / "patterns.json"))

    def test_scan_skips_duplicate_dependency_class(self):
        t = self.db.task("T001")
        t.update(
            state="BLOCKED",
            retryable=False,
            feedback="STUCK: no worker progress for 311s (timeout 300s) in state LAUNCHING_DEV",
            role="dev",
            base_sha=BASE,
        )
        self.db.save(t)
        classes = [item["class_id"] for item in self.loop.scan()]
        self.assertIn("stuck_no_progress", classes)
        self.assertNotIn("queue_dependency_hard_block", classes)

    def test_launching_shell_is_not_a_heal(self):
        for i in range(self.cfg.max_daily_launches):
            self.db.reserve(f"fill-{i}", self.c.day(), self.cfg.max_daily_launches)
        t = self.db.task("T001")
        t.update(
            state="BLOCKED",
            retryable=True,
            attempt=1,
            stuck_retries=4,
            self_heal_blocked=True,
            feedback="STUCK: no worker progress for 311s in state LAUNCHING_DEV",
            role="dev",
            base_sha=BASE,
        )
        self.db.save(t)
        success, fix, _resumed = self.loop.apply_recover_worker(t, t["feedback"])
        self.assertFalse(success)
        self.assertIn("not healed", fix)

    def test_exhausted_block_relaunches_live_run(self):
        t = self.db.task("T001")
        t.update(
            state="BLOCKED",
            retryable=False,
            attempt=1,
            stuck_retries=4,
            self_heal_blocked=True,
            feedback="STUCK: no worker progress for 311s in state LAUNCHING_DEV",
            role="dev",
            base_sha=BASE,
        )
        self.db.save(t)
        success, _fix, resumed = self.loop.apply_recover_worker(t, t["feedback"])
        self.assertTrue(success)
        self.assertEqual(resumed, "T001")
        after = self.db.task("T001")
        self.assertEqual(after["state"], "DEVELOPING")
        self.assertTrue(after.get("run_id"))

    def test_blocked_report_is_not_spammed(self):
        t = self.db.task("T001")
        t.update(
            state="BLOCKED",
            self_heal_blocked=True,
            selfheal_block_reported=True,
            feedback="SELF_HEAL_BLOCKED:stuck_no_progress: STUCK: no worker progress",
        )
        self.db.save(t)
        self.loop.registry.record_attempt("stuck_no_progress", success=False, detail="STUCK")
        self.loop.registry.record_attempt("stuck_no_progress", success=False, detail="STUCK")
        self.loop.registry.record_attempt("stuck_no_progress", success=False, detail="STUCK")
        reports = self.loop.tick()
        self.assertEqual(reports, [])


class PatternCooldownTests(unittest.TestCase):
    def test_three_successes_do_not_permanent_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = PatternRegistry(path=str(Path(tmp) / "p.json"))
            for ok in (False, False, True):
                reg.record_attempt("stuck_no_progress", success=ok, detail="STUCK")
            self.assertFalse(reg.is_blocked("stuck_no_progress"))

    def test_release_cooled_after_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = PatternRegistry(path=str(Path(tmp) / "p.json"))
            for _ in range(MAX_REPAIR_ATTEMPTS):
                reg.record_attempt("stuck_no_progress", success=False, detail="STUCK")
            self.assertTrue(reg.is_blocked("stuck_no_progress"))
            reg.data["classes"]["stuck_no_progress"]["last_seen_at"] = time.time() - 601
            released = reg.release_cooled()
            self.assertIn("stuck_no_progress", released)
            self.assertFalse(reg.is_blocked("stuck_no_progress"))


if __name__ == "__main__":
    unittest.main()
