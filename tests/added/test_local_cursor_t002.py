"""Regression: LocalCursor must deliver T002 under execution/ — not empty T001 recommit."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentops.local_runtime import LocalCursor


class LocalCursorT002Tests(unittest.TestCase):
    def test_write_t002_execution_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cursor = LocalCursor(root, github_repo="owner/lab")
            paths = cursor._write_t002_execution(root)
            self.assertIn("trading_lab/execution/kernel.py", paths)
            self.assertTrue((root / "trading_lab" / "execution" / "kernel.py").is_file())
            self.assertTrue((root / "tests" / "added" / "test_execution_kernel_local_kian.py").is_file())

    def test_commit_adds_marker_when_tree_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cursor = LocalCursor(root)
            calls = []

            def fake_git(args, cwd=None):
                calls.append(list(args))
                if args[:2] == ["status", "--porcelain"]:
                    return ""
                if args[0] == "add":
                    return ""
                if "commit" in args:
                    return ""
                return ""

            with patch.object(cursor, "_git", side_effect=fake_git):
                cursor._commit(root, "test commit")
            self.assertTrue(any(c[:2] == ["status", "--porcelain"] for c in calls))
            self.assertTrue(any(c[0] == "add" for c in calls))
            self.assertTrue(any("commit" in c for c in calls))
            notes = list((root / "docs" / "research").glob("LOCAL_KIAN_DELIVERY_*.md"))
            self.assertEqual(len(notes), 1)


if __name__ == "__main__":
    unittest.main()
