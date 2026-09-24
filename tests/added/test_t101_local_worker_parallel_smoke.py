"""Legacy smoke for issue #10: local worker coexistence behavior."""

import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agentops.local_runtime import LocalCursor


class T101LocalWorkerCoexistenceTests(unittest.TestCase):
    def test_localcursor_can_finish_two_parallel_runs(self) -> None:
        cursor = LocalCursor(Path.cwd())

        def fake_kian(_row: dict) -> dict:
            time.sleep(0.05)
            return {"result": "kian-finished"}

        def fake_negar(_row: dict) -> dict:
            time.sleep(0.05)
            return {"result": "negar-finished"}

        with (
            patch.object(LocalCursor, "_run_kian", side_effect=fake_kian),
            patch.object(LocalCursor, "_run_negar", side_effect=fake_negar),
        ):
            run_kian = cursor.create("dev", "Kian", "", "main", "legacy-smoke", review=False)
            run_negar = cursor.create("qa", "Negar", "", "main", "legacy-smoke", review=True)

            deadline = time.time() + 3.0
            while time.time() < deadline:
                k = cursor.run("dev", run_kian)
                n = cursor.run("qa", run_negar)
                if k["status"] == "FINISHED" and n["status"] == "FINISHED":
                    break
                time.sleep(0.02)

        k_final = cursor.run("dev", run_kian)
        n_final = cursor.run("qa", run_negar)

        self.assertEqual(k_final["status"], "FINISHED")
        self.assertEqual(n_final["status"], "FINISHED")
        self.assertEqual(k_final["result"], "kian-finished")
        self.assertEqual(n_final["result"], "negar-finished")
        self.assertNotEqual(run_kian, run_negar)


if __name__ == "__main__":
    unittest.main()
