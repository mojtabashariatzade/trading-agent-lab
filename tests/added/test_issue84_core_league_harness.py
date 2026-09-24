"""Issue #84 deterministic Core-league evaluation harness tests."""

import unittest

from trading_lab.tournament import (
    CoreLeagueEvaluationError,
    CoreLeagueEvaluationHarness,
)


class Issue84CoreLeagueHarnessTests(unittest.TestCase):
    def test_evaluation_ordering_is_reproducible(self):
        payload = {
            "schema_version": "core-league-candidate-feed.v1",
            "source_selector_schema": "selector-input.v1",
            "candidates": [
                {
                    "contract_id": "S03",
                    "epic_family_id": 3,
                    "variant_id": "S03-V02",
                    "score": 7.6,
                    "promotion_bucket": "runner_up",
                    "promotion_rank": 1,
                },
                {
                    "contract_id": "S01",
                    "epic_family_id": 1,
                    "variant_id": "S01-V03",
                    "score": 8.0,
                    "promotion_bucket": "champion",
                    "promotion_rank": 1,
                },
                {
                    "contract_id": "S02",
                    "epic_family_id": 2,
                    "variant_id": "S02-V01",
                    "score": 7.5,
                    "promotion_bucket": "runner_up",
                    "promotion_rank": 2,
                },
            ],
        }

        harness = CoreLeagueEvaluationHarness()
        first = harness.evaluate(candidate_feed=payload)
        second = harness.evaluate(candidate_feed=payload)

        self.assertEqual(first, second)
        self.assertEqual([row.contract_id for row in first.rows], ["S01", "S03", "S02"])
        self.assertEqual(first.pass_count, 1)
        self.assertEqual(first.wait_count, 2)

    def test_rejects_malformed_payload_with_machine_readable_reasons(self):
        payload = {
            "schema_version": "core-league-candidate-feed.v1",
            "candidates": [
                {
                    "contract_id": "",
                    "epic_family_id": 1,
                    "variant_id": "S01-V01",
                    "score": 1.0,
                    "promotion_bucket": "champion",
                    "promotion_rank": 1,
                }
            ],
        }

        with self.assertRaises(CoreLeagueEvaluationError) as ctx:
            CoreLeagueEvaluationHarness().evaluate(candidate_feed=payload)

        self.assertIn("INVALID_CONTRACT_ID", ctx.exception.reason_codes)

    def test_rejects_duplicate_epic_family_invariant_violation(self):
        payload = {
            "schema_version": "core-league-candidate-feed.v1",
            "candidates": [
                {
                    "contract_id": "S01",
                    "epic_family_id": 1,
                    "variant_id": "S01-V01",
                    "score": 1.0,
                    "promotion_bucket": "champion",
                    "promotion_rank": 1,
                },
                {
                    "contract_id": "S02",
                    "epic_family_id": 1,
                    "variant_id": "S02-V01",
                    "score": 0.8,
                    "promotion_bucket": "runner_up",
                    "promotion_rank": 1,
                },
            ],
        }

        with self.assertRaises(CoreLeagueEvaluationError) as ctx:
            CoreLeagueEvaluationHarness().evaluate(candidate_feed=payload)

        self.assertIn("DUPLICATE_EPIC_FAMILY_ID", ctx.exception.reason_codes)


if __name__ == "__main__":
    unittest.main()
