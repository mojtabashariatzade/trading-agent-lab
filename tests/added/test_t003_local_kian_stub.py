"""Local Kian stub for T003."""
import unittest
from pathlib import Path


class LocalKianStub_T003(unittest.TestCase):
    def test_note_exists(self):
        note = Path(__file__).resolve().parents[2] / "docs" / "research" / "T003_LOCAL_KIAN.md"
        self.assertTrue(note.is_file())


if __name__ == "__main__":
    unittest.main()
