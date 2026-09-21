"""Crash resume: completed durable steps are not re-executed after process restart."""
import tempfile
import unittest
from pathlib import Path

from agentops.config import Settings
from agentops.controller import Controller
from agentops.orchestration.maf_durable.activities import TaskActivities
from agentops.orchestration.maf_durable.checkpoint_store import CheckpointStore
from agentops.orchestration.maf_durable.engine import LocalDurableEngine
from agentops.store import Store
from tests.fakes import *


class MafDurableResumeTests(unittest.TestCase):
    def _engine(self, tmp: str):
        cfg = Settings(
            REPO, "fake-gh", "fake-cursor", "1:fake", 42, frozenset({42}),
            state_path=":memory:", allow_runs=True, spend_limit_confirmed=True,
            protection_confirmed=True, agent_runtime="local",
            orchestration_backend="maf_durable", durable_checkpoint_dir=tmp,
            auto_merge_safe=True,
        )
        db = Store(":memory:")
        db.set("paused", False)
        gh, cu, tg = FakeGitHub(), FakeCursor(), FakeTelegram()
        ctl = Controller(cfg, db, gh, cu, tg, backlog(), clock=Clock())
        store = CheckpointStore(tmp)
        engine = LocalDurableEngine(store, TaskActivities(ctl))
        return cfg, db, gh, cu, ctl, engine, store

    def test_resume_skips_completed_reconcile_and_launch_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            _cfg, db, _gh, cu, ctl, engine, store = self._engine(tmp)
            ctl.handle(update("/resume"))
            rec = engine.start_task("T001", instance_id="T001:proof-resume")
            # Drive until DEVELOPING with run_id (reconcile + launch completed).
            for _ in range(6):
                rec = engine.advance_instance(rec["instance_id"], max_steps=1)
                t = db.task("T001")
                if t.get("run_id") and "prepare_and_launch_dev" in rec.get("completed_steps", []):
                    break
            self.assertTrue(db.task("T001").get("run_id"))
            self.assertIn("reconcile_existing_delivery", rec["completed_steps"])
            self.assertIn("prepare_and_launch_dev", rec["completed_steps"])
            launch_key = f"{rec['instance_id']}:prepare_and_launch_dev"
            launches_before = engine.execution_counts.get(launch_key, 0)
            self.assertGreaterEqual(launches_before, 1)
            completed_before = list(rec["completed_steps"])
            created_before = len(cu.created)

            # Simulate process crash: new engine, same checkpoint store on disk.
            engine2 = LocalDurableEngine(CheckpointStore(tmp), TaskActivities(ctl))
            rec2 = engine2.get(rec["instance_id"])
            self.assertEqual(rec2["completed_steps"], completed_before)
            rec2 = engine2.advance_instance(rec["instance_id"], max_steps=1)
            # Completed launch step must not run again.
            self.assertEqual(engine2.execution_counts.get(launch_key, 0), 0)
            self.assertEqual(len(cu.created), created_before)
            self.assertEqual(rec2["completed_steps"], completed_before)
            # Next incomplete step may wait (await_dev) without clearing history.
            self.assertIn("prepare_and_launch_dev", rec2["completed_steps"])

    def test_reconcile_existing_pr_skips_relaunch_kian(self):
        with tempfile.TemporaryDirectory() as tmp:
            _cfg, db, _gh, cu, ctl, engine, _store = self._engine(tmp)
            ctl.handle(update("/resume"))
            t = db.task("T001")
            t.update(
                state="PENDING",
                pr=7,
                base_sha=BASE,
                head_sha=HEAD,
                run_id=None,
                attempt=1,
            )
            db.save(t)
            rec = engine.start_task("T001", instance_id="T001:reconcile")
            rec = engine.advance_instance(rec["instance_id"], max_steps=3)
            t = db.task("T001")
            self.assertIn(t["state"], {"CI_WAIT", "LAUNCHING_QA", "REVIEWING"})
            self.assertEqual(t.get("pr"), 7)
            # No fresh Kian create for reconcile path (only QA review creates allowed later).
            self.assertTrue(all(item.get("review") for item in cu.created) or t["state"] == "CI_WAIT")


if __name__ == "__main__":
    unittest.main()
