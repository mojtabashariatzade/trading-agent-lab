import tempfile
import unittest
from pathlib import Path

from agentops.selfheal.patterns import PatternRegistry


class SelfHealRegistrySmoke_stuck_no_progress(unittest.TestCase):
    def test_pattern_classifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = PatternRegistry(path=str(Path(tmp) / "patterns.json"))
            class_id = reg.classify("STUCK: no worker progress for 311s (timeout 300s) in state LAUNCHING_DEV")
            self.assertTrue(isinstance(class_id, str) and class_id)


if __name__ == "__main__":
    unittest.main()
