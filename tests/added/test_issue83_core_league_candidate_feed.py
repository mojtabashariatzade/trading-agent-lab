"""Issue #83 deterministic Core-league candidate feed adapter tests."""

import unittest

from trading_lab.tournament import (
    CandidateFeedValidationError,
    CoreLeagueCandidateFeedAdapter,
)


class Issue83CoreLeagueCandidateFeedTests(unittest.TestCase):
    def test_candidate_feed_ordering_is_reproducible(self):
        payload = {
            "schema_version": "selector-input.v1",
            "candidates": [
                {
                    "contract_id": "S02",
                    "epic_family_id": 2,
                    "variant_id": "S02-V01",
                    "score": 7.5,
                    "promotion_bucket": "runner_up",
                    "promotion_rank": 2,
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
                    "contract_id": "S03",
                    "epic_family_id": 3,
                    "variant_id": "S03-V02",
                    "score": 7.6,
                    "promotion_bucket": "runner_up",
                    "promotion_rank": 1,
                },
            ],
            "rejected_families": [],
        }

        adapter = CoreLeagueCandidateFeedAdapter()
        first = adapter.build(selector_input=payload)
        second = adapter.build(selector_input=payload)

        self.assertEqual(first, second)
        self.assertEqual(
            [item.contract_id for item in first.candidates],
            ["S01", "S03", "S02"],
        )
        self.assertEqual(first.schema_version, "core-league-candidate-feed.v1")

    def test_rejects_ineligible_family_payload_with_machine_readable_reason(self):
        payload = {
            "schema_version": "selector-input.v1",
            "candidates": [
                {
                    "contract_id": "S01",
                    "epic_family_id": 1,
                    "variant_id": "S01-V01",
                    "score": 9.0,
                    "promotion_bucket": "champion",
                    "promotion_rank": 1,
                }
            ],
            "rejected_families": [
                {
                    "contract_id": "S09",
                    "reasons": ["PREREQUISITE_UNAVAILABLE:ohlcv_h1"],
                }
            ],
        }

        with self.assertRaises(CandidateFeedValidationError) as ctx:
            CoreLeagueCandidateFeedAdapter().build(selector_input=payload)

        self.assertIn("INELIGIBLE_FAMILIES_PRESENT", ctx.exception.reason_codes)

    def test_rejects_malformed_candidate_payload_with_machine_readable_reasons(self):
        payload = {
            "schema_version": "selector-input.v1",
            "candidates": [
                {
                    "contract_id": "S01",
                    "epic_family_id": 1,
                    "variant_id": "S01-V01",
                    "score": 9.0,
                    "promotion_bucket": "champion",
                    "promotion_rank": 1,
                },
                {
                    "contract_id": "S01",
                    "epic_family_id": 1,
                    "variant_id": "S01-V02",
                    "score": "nan",
                    "promotion_bucket": "runner_up",
                    "promotion_rank": 1,
                },
            ],
            "rejected_families": [],
        }

        with self.assertRaises(CandidateFeedValidationError) as ctx:
            CoreLeagueCandidateFeedAdapter().build(selector_input=payload)

        self.assertIn("DUPLICATE_CANDIDATE_CONTRACT_ID", ctx.exception.reason_codes)


if __name__ == "__main__":
    unittest.main()
