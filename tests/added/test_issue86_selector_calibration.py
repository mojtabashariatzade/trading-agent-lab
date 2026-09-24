"""Issue #86 deterministic selector-calibration harness tests."""

import unittest

from trading_lab.tournament import SelectorCalibrationError, SelectorCalibrationHarness


class Issue86SelectorCalibrationTests(unittest.TestCase):
    def test_calibration_is_reproducible_with_pass_wait_accounting(self):
        payload = {
            "schema_version": "core-league-evaluation.v1",
            "source_candidate_schema": "core-league-candidate-feed.v1",
            "tie_break_fields": [
                "promotion_bucket_priority",
                "promotion_rank",
                "score_desc",
                "contract_id",
                "variant_id",
            ],
            "pass_count": 2,
            "wait_count": 1,
            "rows": [
                {
                    "contract_id": "S03",
                    "epic_family_id": 3,
                    "variant_id": "S03-V01",
                    "score": 5.0,
                    "promotion_bucket": "runner_up",
                    "promotion_rank": 1,
                    "core_rank": 3,
                    "outcome": "WAIT",
                },
                {
                    "contract_id": "S01",
                    "epic_family_id": 1,
                    "variant_id": "S01-V01",
                    "score": 9.0,
                    "promotion_bucket": "champion",
                    "promotion_rank": 1,
                    "core_rank": 1,
                    "outcome": "PASS",
                },
                {
                    "contract_id": "S02",
                    "epic_family_id": 2,
                    "variant_id": "S02-V04",
                    "score": 8.0,
                    "promotion_bucket": "champion",
                    "promotion_rank": 2,
                    "core_rank": 2,
                    "outcome": "PASS",
                },
            ],
        }

        harness = SelectorCalibrationHarness()
        first = harness.calibrate(core_league_artifact=payload)
        second = harness.calibrate(core_league_artifact=payload)

        self.assertEqual(first, second)
        self.assertEqual(first.pass_count, 2)
        self.assertEqual(first.wait_count, 1)
        self.assertEqual(first.eligible_count, 2)
        self.assertEqual([row.contract_id for row in first.rows], ["S01", "S02", "S03"])

        pass_weights = [row.calibrated_weight for row in first.rows if row.outcome == "PASS"]
        wait_weights = [row.calibrated_weight for row in first.rows if row.outcome == "WAIT"]
        self.assertAlmostEqual(sum(pass_weights), 1.0)
        self.assertTrue(all(weight > 0 for weight in pass_weights))
        self.assertEqual(wait_weights, [0.0])

    def test_rejects_malformed_core_artifact_with_machine_readable_reason(self):
        payload = {
            "schema_version": "core-league-evaluation.v1",
            "pass_count": 1,
            "wait_count": 0,
            "rows": [
                {
                    "contract_id": "S01",
                    "epic_family_id": 1,
                    "variant_id": "S01-V01",
                    "score": "bad-score",
                    "core_rank": 1,
                    "outcome": "PASS",
                }
            ],
        }

        with self.assertRaises(SelectorCalibrationError) as ctx:
            SelectorCalibrationHarness().calibrate(core_league_artifact=payload)

        self.assertIn("INVALID_SCORE", ctx.exception.reason_codes)

    def test_rejects_invariant_violation_for_mismatched_counts(self):
        payload = {
            "schema_version": "core-league-evaluation.v1",
            "pass_count": 99,
            "wait_count": 0,
            "rows": [
                {
                    "contract_id": "S01",
                    "epic_family_id": 1,
                    "variant_id": "S01-V01",
                    "score": 2.0,
                    "core_rank": 1,
                    "outcome": "PASS",
                }
            ],
        }

        with self.assertRaises(SelectorCalibrationError) as ctx:
            SelectorCalibrationHarness().calibrate(core_league_artifact=payload)

        self.assertIn("PASS_COUNT_MISMATCH", ctx.exception.reason_codes)


if __name__ == "__main__":
    unittest.main()
