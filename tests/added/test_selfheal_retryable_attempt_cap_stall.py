import unittest
from dataclasses import replace
from agentops.config import Settings
from agentops.controller import Controller
from agentops.store import Store
from tests.fakes import *


class SelfHealAttemptCapTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
