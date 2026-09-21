"""Negar QA evidence validity is tied to exact PR head SHA."""
import os
import tempfile
import unittest
from pathlib import Path

from agentops import qa_evidence


class NegarQaEvidenceTests(unittest.TestCase):
    def test_record_and_validate_by_head_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("NEGAR_QA_DIR")
            os.environ["NEGAR_QA_DIR"] = tmp
            try:
                ev = qa_evidence.record_negar_qa(
                    repo="owner/lab",
                    pr=8,
                    head_sha="abc123def456",
                    verdict="PASS",
                    ci_url="https://example/actions/1",
                    qa_payload={"verdict": "PASS"},
                    now=1800000000.0,
                )
                self.assertEqual(ev["reviewer_role"], "Negar")
                self.assertTrue(ev["not_a_github_human"])
                self.assertTrue(qa_evidence.is_negar_qa_valid(ev, pr=8, head_sha="abc123def456"))
                self.assertFalse(qa_evidence.is_negar_qa_valid(ev, pr=8, head_sha="ffffffffffff"))
                loaded = qa_evidence.load_negar_qa(8, "abc123def456")
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded["pr"], 8)
                self.assertTrue(Path(tmp, "pr-8-abc123def456.json").is_file())
            finally:
                if old is None:
                    os.environ.pop("NEGAR_QA_DIR", None)
                else:
                    os.environ["NEGAR_QA_DIR"] = old


if __name__ == "__main__":
    unittest.main()
