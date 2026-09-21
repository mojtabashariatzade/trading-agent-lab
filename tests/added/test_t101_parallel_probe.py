"""Parallel autonomy probe for T101."""
import unittest
from pathlib import Path


class ParallelProbe_T101(unittest.TestCase):
    def test_note_exists(self):
        note = Path(__file__).resolve().parents[2] / "docs" / "research" / "T101_PARALLEL_PROBE.md"
        self.assertTrue(note.is_file())


if __name__ == "__main__":
    unittest.main()
