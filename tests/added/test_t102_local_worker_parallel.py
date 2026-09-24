"""Legacy smoke for issue #11: verify a second local worker can overlap in time."""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from agentops.local_runtime import LocalCursor


class T102LocalWorkerParallelTests(unittest.TestCase):
    def test_second_worker_can_run_in_parallel(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cursor = LocalCursor(Path(td))

            gate = threading.Lock()
            stats = {"running": 0, "max_running": 0}

            def fake_worker(_row: dict) -> dict:
                with gate:
                    stats["running"] += 1
                    stats["max_running"] = max(stats["max_running"], stats["running"])
                try:
                    time.sleep(0.25)
                    return {"result": "ok", "git": {"branches": []}}
                finally:
                    with gate:
                        stats["running"] -= 1

            # Patch both execution paths so the test does not depend on environment flags.
            cursor._run_kian = fake_worker  # type: ignore[method-assign]
            cursor._run_negar = fake_worker  # type: ignore[method-assign]

            r1 = cursor.create("agent-a", "kian", "repo", "main", "p1", review=False)
            r2 = cursor.create("agent-b", "negar", "repo", "main", "p2", review=True)

            deadline = time.time() + 5
            while time.time() < deadline:
                s1 = cursor.run("agent-a", r1).get("status")
                s2 = cursor.run("agent-b", r2).get("status")
                if s1 == "FINISHED" and s2 == "FINISHED":
                    break
                time.sleep(0.02)

            self.assertEqual(cursor.run("agent-a", r1).get("status"), "FINISHED")
            self.assertEqual(cursor.run("agent-b", r2).get("status"), "FINISHED")
            self.assertGreaterEqual(
                stats["max_running"],
                2,
                "Expected overlapping execution for second local worker launch",
            )


if __name__ == "__main__":
    unittest.main()
