"""Issue #78 deterministic intra-family league harness acceptance tests."""

import unittest

from trading_lab.strategies import default_strategy_family_registry
from trading_lab.tournament import IntraFamilyLeagueHarness


class Issue78IntraFamilyLeagueTests(unittest.TestCase):
    def test_matrix_uses_canonical_registry_and_marks_missing_prerequisites(self):
        harness = IntraFamilyLeagueHarness()
        # Intentionally incomplete to force explicit ineligible reasons.
        available_prerequisites = {"ohlcv_m15": True, "spread_bid_ask": True}

        result = harness.evaluate(available_prerequisites=available_prerequisites)

        self.assertEqual(len(result.matrix), 15)
        self.assertEqual(result.matrix[0].contract_id, "S01")

        s09_row = next(row for row in result.matrix if row.contract_id == "S09")
        self.assertTrue(s09_row.variants)
        first_variant = s09_row.variants[0]
        self.assertFalse(first_variant.eligible)
        self.assertIn("PREREQUISITE_STATUS_UNKNOWN:ohlcv_h1", first_variant.reasons)
        self.assertIn("PREREQUISITE_STATUS_UNKNOWN:ohlcv_h4", first_variant.reasons)

    def test_reproducible_output_for_identical_inputs(self):
        harness = IntraFamilyLeagueHarness()
        available_prerequisites = {
            prerequisite: True
            for definition in default_strategy_family_registry()
            for prerequisite in definition.data_prerequisites
        }

        scores = {
            "S01": {"S01-V01": 1.0, "S01-V02": 2.0},
            "S02": {"S02-V01": 0.5},
        }
        first = harness.evaluate(
            available_prerequisites=available_prerequisites,
            variant_scores=scores,
        )
        second = harness.evaluate(
            available_prerequisites=available_prerequisites,
            variant_scores=scores,
        )

        self.assertEqual(first, second)

    def test_ranking_order_is_invariant_to_mapping_input_order(self):
        registry = default_strategy_family_registry()
        # Same key-values, different insertion order.
        prereq_order_a = {
            prerequisite: True
            for definition in registry
            for prerequisite in definition.data_prerequisites
        }
        prereq_order_b = {
            prerequisite: prereq_order_a[prerequisite]
            for prerequisite in reversed(tuple(prereq_order_a.keys()))
        }

        scores_order_a = {"S01": {"S01-V01": 1.0, "S01-V02": 3.0, "S01-V03": 2.0}}
        scores_order_b = {"S01": {"S01-V03": 2.0, "S01-V01": 1.0, "S01-V02": 3.0}}

        harness = IntraFamilyLeagueHarness()
        result_a = harness.evaluate(
            available_prerequisites=prereq_order_a,
            variant_scores=scores_order_a,
        )
        result_b = harness.evaluate(
            available_prerequisites=prereq_order_b,
            variant_scores=scores_order_b,
        )

        self.assertEqual(result_a, result_b)

        s01_ranked = dict(result_a.ranked_by_family)["S01"]
        self.assertGreaterEqual(len(s01_ranked), 3)
        self.assertEqual(
            tuple(item.variant_id for item in s01_ranked[:3]),
            ("S01-V02", "S01-V03", "S01-V01"),
        )


if __name__ == "__main__":
    unittest.main()
