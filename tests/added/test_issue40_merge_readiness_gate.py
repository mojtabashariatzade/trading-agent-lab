"""Deterministic repository-level merge-readiness gate for required checks/reviews."""

import unittest

from trading_lab.research.merge_gate import (
    MergeGateEvaluationInput,
    RequiredCheckStatus,
    evaluate_merge_readiness,
)


class Issue40MergeReadinessGateTests(unittest.TestCase):
    def _base_input(self, **overrides) -> MergeGateEvaluationInput:
        values = {
            "repository": "mojtabashariatzade/trading-agent-lab",
            "pr_number": 51,
            "required_checks": (
                RequiredCheckStatus(name="qa", conclusion="SUCCESS"),
                RequiredCheckStatus(name="unit-tests", conclusion="SUCCESS"),
            ),
            "review_decision": "APPROVED",
            "override_approved": False,
            "override_rationale": None,
        }
        values.update(overrides)
        return MergeGateEvaluationInput(**values)

    def test_failing_required_check_blocks_merge_readiness(self):
        result = evaluate_merge_readiness(
            self._base_input(
                required_checks=(
                    RequiredCheckStatus(name="qa", conclusion="SUCCESS"),
                    RequiredCheckStatus(name="unit-tests", conclusion="FAILURE"),
                )
            )
        )
        self.assertFalse(result.merge_ready)
        self.assertIn("REQUIRED_CHECKS_FAILED", result.block_codes)
        self.assertIn("unit-tests", result.failed_required_checks)

    def test_missing_required_review_blocks_merge_readiness(self):
        result = evaluate_merge_readiness(self._base_input(review_decision="REVIEW_REQUIRED"))
        self.assertFalse(result.merge_ready)
        self.assertIn("REQUIRED_REVIEW_MISSING", result.block_codes)

    def test_override_requires_explicit_rationale(self):
        result = evaluate_merge_readiness(
            self._base_input(
                review_decision="REVIEW_REQUIRED",
                override_approved=True,
                override_rationale="   ",
            )
        )
        self.assertFalse(result.merge_ready)
        self.assertIn("OVERRIDE_RATIONALE_REQUIRED", result.block_codes)
        self.assertFalse(result.override_applied)

    def test_override_with_rationale_can_unblock_and_records_reason(self):
        result = evaluate_merge_readiness(
            self._base_input(
                required_checks=(RequiredCheckStatus(name="qa", conclusion="FAILURE"),),
                review_decision="REVIEW_REQUIRED",
                override_approved=True,
                override_rationale="Owner approved temporary bypass for infra outage; tracked in incident #123.",
            )
        )
        self.assertTrue(result.merge_ready)
        self.assertTrue(result.override_applied)
        self.assertEqual(
            result.override_rationale,
            "Owner approved temporary bypass for infra outage; tracked in incident #123.",
        )
        self.assertIn("REQUIRED_CHECKS_FAILED", result.block_codes)
        self.assertIn("REQUIRED_REVIEW_MISSING", result.block_codes)


if __name__ == "__main__":
    unittest.main()
