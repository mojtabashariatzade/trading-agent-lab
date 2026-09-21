"""Parallel autonomy probe for T102."""
import unittest
from pathlib import Path


class ParallelProbe_T102(unittest.TestCase):
    def test_note_exists(self):
        note = Path(__file__).resolve().parents[2] / "docs" / "research" / "T102_PARALLEL_PROBE.md"
        self.assertTrue(note.is_file())


if __name__ == "__main__":
    unittest.main()
