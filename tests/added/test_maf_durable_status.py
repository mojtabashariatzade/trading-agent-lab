"""Status honesty for maf_durable: no fake RUNNING without durable worker execution id."""
import unittest

from agentops.runtime_status import build_status
from agentops.store import Store
from tests.fakes import NOW


class MafDurableStatusTests(unittest.TestCase):
    def test_developing_without_durable_id_is_not_running(self):
        db = Store(":memory:")
        db.set("paused", False)
        db.save(
            {
                "id": "T101",
                "state": "DEVELOPING",
                "role": "dev",
                "run_id": "local-run-abc",
                "attempt": 1,
                "phase": 1,
            }
        )
        payload = build_status(
            db,
            pid=1,
            process_alive=True,
            auto_merge_safe=True,
            now=float(NOW),
            orchestration_backend="maf_durable",
            durable_runtime="local_checkpoint",
        )
        self.assertNotEqual(payload["status"], "RUNNING")
        self.assertEqual(payload["orchestration_backend"], "maf_durable")
        self.assertIsNone(payload.get("current_agent"))

    def test_developing_with_durable_running_is_running(self):
        db = Store(":memory:")
        db.set("paused", False)
        db.save(
            {
                "id": "T101",
                "state": "DEVELOPING",
                "role": "dev",
                "run_id": "local-run-abc",
                "durable_instance_id": "T101:abc",
                "durable_status": "Running",
                "attempt": 1,
                "phase": 1,
            }
        )
        payload = build_status(
            db,
            pid=1,
            process_alive=True,
            auto_merge_safe=True,
            now=float(NOW),
            orchestration_backend="maf_durable",
            durable_runtime="local_checkpoint",
        )
        self.assertEqual(payload["status"], "RUNNING")
        self.assertEqual(payload["run_id"], "local-run-abc")
        self.assertEqual(payload["durable_instance_id"], "T101:abc")
        self.assertEqual(payload["current_agent"], "Kian")

    def test_legacy_unchanged_without_durable_fields(self):
        db = Store(":memory:")
        db.set("paused", False)
        db.save(
            {
                "id": "T001",
                "state": "DEVELOPING",
                "role": "dev",
                "run_id": "run-1",
                "attempt": 1,
                "phase": 1,
            }
        )
        payload = build_status(
            db,
            pid=1,
            process_alive=True,
            auto_merge_safe=True,
            now=float(NOW),
            orchestration_backend="legacy",
        )
        self.assertEqual(payload["status"], "RUNNING")
        self.assertEqual(payload["orchestration_backend"], "legacy")


if __name__ == "__main__":
    unittest.main()
