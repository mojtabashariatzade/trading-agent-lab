"""Issue #87 deterministic selector ablation/comparison tests."""

import unittest

from trading_lab.tournament import SelectorAblationError, SelectorAblationHarness


class Issue87SelectorAblationTests(unittest.TestCase):
    def test_comparison_is_reproducible_with_deterministic_mode_ordering(self):
        payload = {
            "schema_version": "selector-calibration.v1",
            "source_core_schema": "core-league-evaluation.v1",
            "tie_break_fields": ["core_rank", "contract_id", "variant_id"],
            "pass_count": 2,
            "wait_count": 1,
            "eligible_count": 2,
            "rows": [
                {
                    "contract_id": "S03",
                    "epic_family_id": 3,
                    "variant_id": "S03-V01",
                    "core_rank": 3,
                    "outcome": "WAIT",
                    "eligible": False,
                    "calibrated_weight": 0.0,
                    "audit_flags": ["INELIGIBLE_WAIT"],
                },
                {
                    "contract_id": "S01",
                    "epic_family_id": 1,
                    "variant_id": "S01-V01",
                    "core_rank": 1,
                    "outcome": "PASS",
                    "eligible": True,
                    "calibrated_weight": 2.0 / 3.0,
                    "audit_flags": ["ELIGIBLE_PASS"],
                },
                {
                    "contract_id": "S02",
                    "epic_family_id": 2,
                    "variant_id": "S02-V01",
                    "core_rank": 2,
                    "outcome": "PASS",
                    "eligible": True,
                    "calibrated_weight": 1.0 / 3.0,
                    "audit_flags": ["ELIGIBLE_PASS"],
                },
            ],
        }

        harness = SelectorAblationHarness()
        first = harness.compare(calibration_artifact=payload)
        second = harness.compare(calibration_artifact=payload)

        self.assertEqual(first, second)
        self.assertEqual(len(first.rows), 3)
        self.assertEqual([row.rank for row in first.rows], [1, 2, 3])
        self.assertEqual(
            [row.mode_id for row in first.rows],
            ["fixed_single_specialist", "calibrated_selector", "blended_fallback"],
        )

    def test_rejects_malformed_payload_with_machine_readable_reason_codes(self):
        payload = {
            "schema_version": "selector-calibration.v1",
            "pass_count": 1,
            "wait_count": 0,
            "eligible_count": 1,
            "rows": [
                {
                    "contract_id": "S01",
                    "core_rank": 1,
                    "outcome": "PASS",
                    "eligible": True,
                    "calibrated_weight": "bad-weight",
                }
            ],
        }

        with self.assertRaises(SelectorAblationError) as ctx:
            SelectorAblationHarness().compare(calibration_artifact=payload)

        self.assertIn("INVALID_CALIBRATED_WEIGHT", ctx.exception.reason_codes)

    def test_rejects_metric_shape_invariant_mismatch(self):
        payload = {
            "schema_version": "selector-calibration.v1",
            "pass_count": 2,
            "wait_count": 0,
            "eligible_count": 2,
            "rows": [
                {
                    "contract_id": "S01",
                    "core_rank": 1,
                    "outcome": "PASS",
                    "eligible": True,
                    "calibrated_weight": 0.25,
                },
                {
                    "contract_id": "S02",
                    "core_rank": 2,
                    "outcome": "PASS",
                    "eligible": True,
                    "calibrated_weight": 0.25,
                },
            ],
        }

        with self.assertRaises(SelectorAblationError) as ctx:
            SelectorAblationHarness().compare(calibration_artifact=payload)

        self.assertIn("PASS_WEIGHT_SUM_MISMATCH", ctx.exception.reason_codes)


if __name__ == "__main__":
    unittest.main()
