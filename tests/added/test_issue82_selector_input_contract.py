"""Issue #82 deterministic selector-input contract acceptance tests."""

import unittest

from trading_lab.strategies import default_strategy_family_registry
from trading_lab.tournament import IntraFamilyLeagueHarness
from trading_lab.tournament.inter_family import (
    FamilyChampion,
    IneligibleFamily,
    InterFamilyChampionshipHarness,
    InterFamilyChampionshipResult,
    PromotionContract,
)
from trading_lab.tournament.selector_input import SelectorInputContractHarness


class Issue82SelectorInputContractTests(unittest.TestCase):
    def test_build_is_reproducible_for_identical_championship_input(self):
        available_prerequisites = {
            prerequisite: True
            for definition in default_strategy_family_registry()
            for prerequisite in definition.data_prerequisites
        }
        available_prerequisites["ohlcv_h1"] = False

        intra = IntraFamilyLeagueHarness().evaluate(
            available_prerequisites=available_prerequisites,
            variant_scores={
                "S01": {"S01-V01": 10.0},
                "S02": {"S02-V01": 8.5},
                "S03": {"S03-V01": 7.0},
            },
        )
        championship = InterFamilyChampionshipHarness().evaluate(
            intra_family_result=intra,
            champion_slots=1,
            runner_up_slots=2,
        )

        harness = SelectorInputContractHarness()
        first = harness.build(championship_result=championship)
        second = harness.build(championship_result=championship)

        self.assertEqual(first, second)

    def test_malformed_input_is_rejected_with_explicit_validation_errors(self):
        malformed_duplicate = InterFamilyChampionshipResult(
            championship_ranking=(
                FamilyChampion("S01", 1, "S01-V01", 9.0),
                FamilyChampion("S02", 2, "S02-V01", 8.0),
            ),
            promotion=PromotionContract(
                selected_champions=(FamilyChampion("S01", 1, "S01-V01", 9.0),),
                runner_ups=(FamilyChampion("S01", 1, "S01-V02", 8.0),),
                ineligible_families=(IneligibleFamily("S09", ("PREREQUISITE_UNAVAILABLE:ohlcv_h1",)),),
            ),
        )
        with self.assertRaisesRegex(ValueError, "duplicate promoted contract_id"):
            SelectorInputContractHarness().build(championship_result=malformed_duplicate)

        malformed_reasonless = InterFamilyChampionshipResult(
            championship_ranking=(FamilyChampion("S01", 1, "S01-V01", 9.0),),
            promotion=PromotionContract(
                selected_champions=(FamilyChampion("S01", 1, "S01-V01", 9.0),),
                runner_ups=(),
                ineligible_families=(IneligibleFamily("S09", ("ALL_PREREQUISITES_AVAILABLE",)),),
            ),
        )
        with self.assertRaisesRegex(ValueError, "requires explicit reasons"):
            SelectorInputContractHarness().build(championship_result=malformed_reasonless)

    def test_to_dict_schema_contains_required_fields_and_invariants(self):
        available_prerequisites = {
            prerequisite: True
            for definition in default_strategy_family_registry()
            for prerequisite in definition.data_prerequisites
        }
        available_prerequisites["official_macro_release_feed"] = False

        intra = IntraFamilyLeagueHarness().evaluate(
            available_prerequisites=available_prerequisites,
            variant_scores={"S01": {"S01-V01": 6.0}, "S02": {"S02-V01": 5.0}},
        )
        championship = InterFamilyChampionshipHarness().evaluate(
            intra_family_result=intra,
            champion_slots=1,
            runner_up_slots=1,
        )

        contract = SelectorInputContractHarness().build(championship_result=championship)
        payload = contract.to_dict()

        self.assertEqual(payload["schema_version"], "selector-input.v1")
        self.assertIsInstance(payload["candidates"], list)
        self.assertGreaterEqual(len(payload["candidates"]), 1)

        candidate = payload["candidates"][0]
        self.assertEqual(
            set(candidate.keys()),
            {
                "contract_id",
                "epic_family_id",
                "variant_id",
                "score",
                "promotion_bucket",
                "promotion_rank",
            },
        )

        self.assertIsInstance(payload["rejected_families"], list)
        for row in payload["rejected_families"]:
            self.assertEqual(set(row.keys()), {"contract_id", "reasons"})
            self.assertTrue(row["reasons"])


if __name__ == "__main__":
    unittest.main()
