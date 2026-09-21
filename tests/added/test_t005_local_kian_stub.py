"""Local Kian stub for T005."""
import unittest
from pathlib import Path


class LocalKianStub_T005(unittest.TestCase):
    def test_note_exists(self):
        note = Path(__file__).resolve().parents[2] / "docs" / "research" / "T005_LOCAL_KIAN.md"
        self.assertTrue(note.is_file())


if __name__ == "__main__":
    unittest.main()
