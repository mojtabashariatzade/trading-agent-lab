"""Proof tests for hands-off execution: quota, resume, queue, stuck, restart."""
import unittest
from dataclasses import replace

from agentops.config import Settings
from agentops.controller import Controller
from agentops.store import Store
from tests.fakes import *


def mixed_backlog():
    return [
        backlog()[0],
        {
            "id": "T00A",
            "title": "Independent phase-1 task",
            "description": "Does not depend on T001.",
            "acceptance": ["Independent"],
            "allowed_prefixes": ["docs/research/"],
            "depends_on": [],
            "phase": 1,
        },
        {
            "id": "T00B",
            "title": "Depends on T001",
            "description": "Must wait for T001 DONE.",
            "acceptance": ["After T001"],
            "allowed_prefixes": ["docs/research/"],
            "depends_on": ["T001"],
            "phase": 1,
        },
        backlog()[1],
    ]


class AutonomousExecutionTests(unittest.TestCase):
    def _ctrl(self, **cfg_kw):
        cfg = Settings(
            REPO, "fake-gh", "fake-cursor", "1:fake", 42, frozenset({42}),
            state_path=":memory:", allow_runs=True, spend_limit_confirmed=True,
            protection_confirmed=True, autonomous_default=False, auto_merge_safe=True,
            max_attempts=2, max_stuck_retries=3, stuck_backoff_seconds=5,
            stuck_timeout_seconds=300, max_daily_launches=4, **cfg_kw,
        )
        db = Store(":memory:")
        gh, cu, tg = FakeGitHub(), FakeCursor(), FakeTelegram()
        clock = Clock()
        ctl = Controller(cfg, db, gh, cu, tg, mixed_backlog(), clock=clock)
        return cfg, db, gh, cu, tg, clock, ctl

    def test_local_runtime_does_not_use_daily_wall(self):
        _cfg, db, _gh, cu, _tg, _clock, ctl = self._ctrl(agent_runtime="local")
        for i in range(4):
            self.assertTrue(db.reserve(f"old-{i}", ctl.day(), 4))
        ctl.handle(update("/resume"))
        ctl.tick()
        t = db.task("T001")
        self.assertEqual(t["state"], "DEVELOPING")
        self.assertTrue(t.get("run_id"))
        self.assertEqual(len(cu.created), 1)

    def test_ready_pr_resumes_at_ci_not_new_kian(self):
        _cfg, db, _gh, cu, _tg, _clock, ctl = self._ctrl()
        ctl.handle(update("/resume"))
        t = db.task("T001")
        t.update(
            state="LAUNCHING_DEV",
            role="dev",
            attempt=2,
            pr=7,
            base_sha=BASE,
            head_sha=HEAD,
            run_id=None,
            agent_id=None,
        )
        db.save(t)
        created_before = len(cu.created)
        ctl.tick()
        t = db.task("T001")
        self.assertIn(t["state"], {"CI_WAIT", "LAUNCHING_QA", "REVIEWING"})
        self.assertEqual(t.get("pr"), 7)
        self.assertEqual(t.get("head_sha"), HEAD)
        new = cu.created[created_before:]
        self.assertTrue(all(item.get("review") for item in new))

    def test_ci_wait_does_not_freeze_independent_task(self):
        _cfg, db, gh, cu, _tg, _clock, ctl = self._ctrl()
        gh.ci_result = "WAIT"
        ctl.handle(update("/resume"))
        t = db.task("T001")
        t.update(state="CI_WAIT", pr=7, head_sha=HEAD, base_sha=BASE, role="dev", ci_wait_at=_clock.now)
        db.save(t)
        ctl.tick()
        self.assertEqual(db.task("T001")["state"], "CI_WAIT")
        self.assertEqual(db.task("T00A")["state"], "DEVELOPING")
        self.assertEqual(db.task("T00B")["state"], "PENDING")
        self.assertTrue(cu.created)

    def test_exhausted_task_does_not_freeze_independent(self):
        _cfg, db, _gh, _cu, _tg, _clock, ctl = self._ctrl()
        ctl.handle(update("/resume"))
        t = db.task("T001")
        t.update(
            state="BLOCKED",
            retryable=False,
            stuck_retries=4,
            self_heal_blocked=True,
            feedback="STUCK: no worker progress",
            role="dev",
        )
        db.save(t)
        ctl.tick()
        self.assertEqual(db.task("T001")["state"], "BLOCKED")
        self.assertEqual(db.task("T00A")["state"], "DEVELOPING")
        self.assertEqual(db.task("T00B")["state"], "PENDING")

    def test_missing_last_progress_uses_launch_at(self):
        _cfg, db, _gh, _cu, _tg, clock, ctl = self._ctrl()
        ctl.handle(update("/resume"))
        t = db.task("T001")
        t.update(
            state="LAUNCHING_DEV",
            run_id=None,
            last_progress_at=None,
            launch_at=clock.now - 91,
            backoff_until=0,
            progress_fingerprint="stale",
        )
        t.pop("last_progress_at", None)
        db.save(t)
        ctl.tick()
        t = db.task("T001")
        self.assertGreaterEqual(int(t.get("stuck_retries", 0)), 1)

    def test_live_running_worker_not_killed_at_stuck_timeout(self):
        _cfg, db, _gh, cu, _tg, clock, ctl = self._ctrl()
        ctl.handle(update("/resume"))
        ctl.tick()
        t = db.task("T001")
        t["last_progress_at"] = clock.now - 301
        db.save(t)
        ctl.cfg = replace(ctl.cfg, stuck_timeout_seconds=300)
        ctl.tick()
        t = db.task("T001")
        self.assertEqual(t["state"], "DEVELOPING")
        self.assertEqual(int(t.get("stuck_retries", 0)), 0)
        self.assertEqual(cu.runs[t["run_id"]]["status"], "RUNNING")

    def test_restart_preserves_stuck_retries_and_launch_rows(self):
        cfg, db, gh, cu, tg, clock, ctl = self._ctrl()
        ctl.handle(update("/resume"))
        ctl.tick()
        t = db.task("T001")
        t["stuck_retries"] = 2
        db.save(t)
        db.reserve("keep-me", ctl.day(), 4)
        before = db.launch_count(ctl.day())
        ctl2 = Controller(cfg, db, gh, cu, tg, mixed_backlog(), clock=clock)
        t2 = ctl2.db.task("T001")
        self.assertEqual(int(t2.get("stuck_retries", 0)), 2)
        self.assertEqual(ctl2.db.launch_count(ctl2.day()), before)

    def test_two_task_dependency_order_hands_off(self):
        cfg, db, gh, cu, tg, clock, ctl = self._ctrl()
        ctl.handle(update("/resume"))
        ctl.tick()
        t = db.task("T001")
        cu.finish_dev(t["run_id"])
        ctl.tick()
        ctl.tick()
        t = db.task("T001")
        self.assertEqual(t["state"], "REVIEWING")
        cu.finish_qa(t["run_id"])
        ctl.tick()
        self.assertEqual(db.task("T001")["state"], "DONE")
        ctl.tick()
        self.assertEqual(db.task("T00A")["state"], "DEVELOPING")
        self.assertEqual(db.task("T00B")["state"], "PENDING")


if __name__ == "__main__":
    unittest.main()
