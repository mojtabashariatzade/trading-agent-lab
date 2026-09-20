import tempfile
import unittest
from pathlib import Path

from agentops.selfheal.patterns import PatternRegistry


class SelfHealRegistrySmoke_queue_dependency_hard_block(unittest.TestCase):
    def test_pattern_classifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = PatternRegistry(path=str(Path(tmp) / "patterns.json"))
            class_id = reg.classify("dependency_hard_block: T002 waits on T001 (Cursor terminal/unknown status: ERROR)")
            self.assertTrue(isinstance(class_id, str) and class_id)


if __name__ == "__main__":
    unittest.main()
