"""Issue #80 deterministic inter-family championship acceptance tests."""

import unittest

from trading_lab.strategies import default_strategy_family_registry
from trading_lab.tournament import IntraFamilyLeagueHarness
from trading_lab.tournament.inter_family import InterFamilyChampionshipHarness


class Issue80InterFamilyChampionshipTests(unittest.TestCase):
    def test_reproducible_cross_family_ranking_for_identical_inputs(self):
        available_prerequisites = {
            prerequisite: True
            for definition in default_strategy_family_registry()
            for prerequisite in definition.data_prerequisites
        }
        intra = IntraFamilyLeagueHarness().evaluate(
            available_prerequisites=available_prerequisites,
            variant_scores={
                "S01": {"S01-V01": 8.0},
                "S02": {"S02-V01": 7.0},
                "S03": {"S03-V01": 6.0},
            },
        )

        harness = InterFamilyChampionshipHarness()
        first = harness.evaluate(intra_family_result=intra)
        second = harness.evaluate(intra_family_result=intra)

        self.assertEqual(first, second)

    def test_ties_are_broken_by_contract_then_variant_id(self):
        available_prerequisites = {
            prerequisite: True
            for definition in default_strategy_family_registry()
            for prerequisite in definition.data_prerequisites
        }
        intra = IntraFamilyLeagueHarness().evaluate(
            available_prerequisites=available_prerequisites,
            variant_scores={
                "S01": {"S01-V01": 5.0},
                "S02": {"S02-V01": 5.0},
            },
        )

        result = InterFamilyChampionshipHarness().evaluate(
            intra_family_result=intra,
            champion_slots=2,
            runner_up_slots=0,
        )

        self.assertGreaterEqual(len(result.championship_ranking), 2)
        self.assertEqual(result.championship_ranking[0].contract_id, "S01")
        self.assertEqual(result.championship_ranking[1].contract_id, "S02")

    def test_promotion_contract_exposes_non_redundant_runner_ups_and_ineligible_reasons(self):
        available_prerequisites = {
            prerequisite: True
            for definition in default_strategy_family_registry()
            for prerequisite in definition.data_prerequisites
        }
        available_prerequisites["ohlcv_h1"] = False
        available_prerequisites["ohlcv_h4"] = False

        intra = IntraFamilyLeagueHarness().evaluate(
            available_prerequisites=available_prerequisites,
            variant_scores={
                "S01": {"S01-V01": 9.0},
                "S05": {"S05-V01": 8.0},  # same epic family as S01
                "S02": {"S02-V01": 7.0},
            },
        )

        result = InterFamilyChampionshipHarness().evaluate(
            intra_family_result=intra,
            champion_slots=1,
            runner_up_slots=2,
        )

        self.assertEqual(tuple(item.contract_id for item in result.promotion.selected_champions), ("S01",))
        self.assertNotIn("S05", tuple(item.contract_id for item in result.promotion.runner_ups))
        self.assertIn("S02", tuple(item.contract_id for item in result.promotion.runner_ups))

        ineligible = {
            item.contract_id: item.reasons for item in result.promotion.ineligible_families
        }
        self.assertIn("S09", ineligible)
        self.assertIn("PREREQUISITE_UNAVAILABLE:ohlcv_h1", ineligible["S09"])
        self.assertIn("PREREQUISITE_UNAVAILABLE:ohlcv_h4", ineligible["S09"])


if __name__ == "__main__":
    unittest.main()
