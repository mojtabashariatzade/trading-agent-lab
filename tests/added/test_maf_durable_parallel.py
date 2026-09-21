"""Parallel durable instances: two independent tasks get distinct ids; waiting does not block."""
import tempfile
import unittest

from agentops.config import Settings
from agentops.controller import Controller
from agentops.orchestration.maf_durable.backend import MafDurableBackend
from agentops.orchestration.maf_durable.activities import TaskActivities
from agentops.orchestration.maf_durable.checkpoint_store import CheckpointStore
from agentops.orchestration.maf_durable.engine import LocalDurableEngine
from agentops.selfheal import MaintenanceLoop
from agentops.store import Store
from pathlib import Path
from tests.fakes import *


def parallel_backlog():
    return [
        {
            "id": "T101",
            "title": "Parallel probe A",
            "description": "Independent",
            "acceptance": ["A"],
            "allowed_prefixes": ["docs/research/"],
            "depends_on": [],
            "phase": 1,
        },
        {
            "id": "T102",
            "title": "Parallel probe B",
            "description": "Independent",
            "acceptance": ["B"],
            "allowed_prefixes": ["docs/research/"],
            "depends_on": [],
            "phase": 1,
        },
        {
            "id": "T103",
            "title": "Depends on T101",
            "description": "Must wait",
            "acceptance": ["After"],
            "allowed_prefixes": ["docs/research/"],
            "depends_on": ["T101"],
            "phase": 1,
        },
    ]


class MafDurableParallelTests(unittest.TestCase):
    def test_two_independent_tasks_get_distinct_durable_and_run_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Settings(
                REPO, "fake-gh", "fake-cursor", "1:fake", 42, frozenset({42}),
                state_path=":memory:", allow_runs=True, spend_limit_confirmed=True,
                protection_confirmed=True, agent_runtime="local",
                orchestration_backend="maf_durable", durable_checkpoint_dir=tmp,
            )
            db = Store(":memory:")
            gh, cu, tg = FakeGitHub(), FakeCursor(), FakeTelegram()
            ctl = Controller(cfg, db, gh, cu, tg, parallel_backlog(), clock=Clock())
            healer = MaintenanceLoop(cfg, db, ctl, Path("."))
            engine = LocalDurableEngine(CheckpointStore(tmp), TaskActivities(ctl))
            backend = MafDurableBackend(cfg, ctl, healer, engine=engine)
            ctl.handle(update("/resume"))
            for _ in range(8):
                backend.tick()
            t101 = db.task("T101")
            t102 = db.task("T102")
            self.assertTrue(t101.get("run_id"), t101)
            self.assertTrue(t102.get("run_id"), t102)
            self.assertNotEqual(t101["run_id"], t102["run_id"])
            self.assertTrue(t101.get("durable_instance_id"))
            self.assertTrue(t102.get("durable_instance_id"))
            self.assertNotEqual(t101["durable_instance_id"], t102["durable_instance_id"])
            self.assertEqual(db.task("T103")["state"], "PENDING")

    def test_ci_wait_does_not_block_second_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Settings(
                REPO, "fake-gh", "fake-cursor", "1:fake", 42, frozenset({42}),
                state_path=":memory:", allow_runs=True, spend_limit_confirmed=True,
                protection_confirmed=True, agent_runtime="local",
                orchestration_backend="maf_durable", durable_checkpoint_dir=tmp,
            )
            db = Store(":memory:")
            gh, cu, tg = FakeGitHub(), FakeCursor(), FakeTelegram()
            gh.ci_result = "WAIT"
            ctl = Controller(cfg, db, gh, cu, tg, parallel_backlog(), clock=Clock())
            healer = MaintenanceLoop(cfg, db, ctl, Path("."))
            engine = LocalDurableEngine(CheckpointStore(tmp), TaskActivities(ctl))
            backend = MafDurableBackend(cfg, ctl, healer, engine=engine)
            ctl.handle(update("/resume"))
            # Put T101 into CI_WAIT occupying no coding slot.
            t = db.task("T101")
            t.update(
                state="CI_WAIT",
                pr=7,
                head_sha=HEAD,
                base_sha=BASE,
                role="dev",
                ci_wait_at=Clock().now,
                run_id=None,
                durable_instance_id="T101:ci",
                durable_status="Running",
                durable_current_step="ci_wait",
            )
            db.save(t)
            engine.store.create(task_id="T101", instance_id="T101:ci")
            rec = engine.store.get("T101:ci")
            rec["completed_steps"] = [
                "reconcile_existing_delivery",
                "prepare_and_launch_dev",
                "await_dev_worker",
            ]
            rec["current_step"] = "ci_wait"
            engine.store.save(rec)
            backend.tick()
            self.assertEqual(db.task("T101")["state"], "CI_WAIT")
            t102 = db.task("T102")
            self.assertIn(t102["state"], {"DEVELOPING", "LAUNCHING_DEV"})
            self.assertTrue(t102.get("run_id") or t102.get("durable_instance_id"))


if __name__ == "__main__":
    unittest.main()
