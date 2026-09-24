"""Acceptance tests for Issue #38 family registry eligibility helpers."""

import unittest

from trading_lab.strategies import (
    FamilyEligibility,
    FamilyRedundancyGroup,
    default_strategy_family_registry,
    family_definition_by_contract_id,
    family_eligibility_matrix,
    family_redundancy_groups,
    validated_strategy_family_registry,
)


class T007FamilyRegistryTests(unittest.TestCase):
    def test_validated_registry_has_all_contract_ids_once(self):
        registry = validated_strategy_family_registry()
        self.assertEqual(len(registry), 15)
        self.assertEqual([item.contract_id for item in registry], [f"S{i:02d}" for i in range(1, 16)])

    def test_lookup_by_contract_id_is_case_and_space_tolerant(self):
        entry = family_definition_by_contract_id(" s04 ")
        self.assertEqual(entry.contract_id, "S04")
        self.assertEqual(entry.epic_family_id, 3)
        self.assertEqual(entry.epic_family_name, "Session-range breakout")
        with self.assertRaises(KeyError):
            family_definition_by_contract_id("S99")

    def test_eligibility_matrix_marks_missing_prerequisites(self):
        available = {
            "ohlcv_m15",
            "spread_bid_ask",
            "iana_timezone_rules",
            "ohlcv_h1",
            "ohlcv_h4",
            "cross_pair_ohlcv_m15",
            "event_calendar_pti",
        }
        matrix = family_eligibility_matrix(available_prerequisites=available)
        by_id = {item.contract_id: item for item in matrix}

        self.assertTrue(by_id["S01"].eligible)
        self.assertTrue(by_id["S04"].eligible)
        self.assertTrue(by_id["S09"].eligible)
        self.assertTrue(by_id["S10"].eligible)

        self.assertFalse(by_id["S11"].eligible)
        self.assertIn("policy_rate_series_pti", by_id["S11"].missing_prerequisites)
        self.assertFalse(by_id["S12"].eligible)
        self.assertIn("official_uk_releases_pti", by_id["S12"].missing_prerequisites)
        self.assertFalse(by_id["S14"].eligible)
        self.assertIn("official_central_bank_text_pti", by_id["S14"].missing_prerequisites)

    def test_eligibility_record_normalizes_missing_prerequisites(self):
        item = FamilyEligibility(
            contract_id="S01",
            eligible=False,
            missing_prerequisites=("", "ohlcv_m15", "ohlcv_m15", "spread_bid_ask"),
            missing_regime_filters=("", "spread_max_pips", "spread_max_pips"),
        )
        self.assertEqual(item.missing_prerequisites, ("ohlcv_m15", "spread_bid_ask"))
        self.assertEqual(item.missing_regime_filters, ("spread_max_pips",))
        self.assertEqual(
            item.blocking_reasons,
            (
                "missing_prerequisite:ohlcv_m15",
                "missing_prerequisite:spread_bid_ask",
                "missing_regime_filter:spread_max_pips",
            ),
        )

        with self.assertRaises(ValueError):
            FamilyEligibility(
                contract_id="S01",
                eligible=True,
                missing_prerequisites=("ohlcv_m15",),
            )

        with self.assertRaises(ValueError):
            FamilyEligibility(
                contract_id="S01",
                eligible=True,
                missing_prerequisites=(),
                horizon_eligible=False,
            )

        with self.assertRaises(ValueError):
            FamilyEligibility(
                contract_id="S01",
                eligible=False,
                missing_prerequisites=(),
                horizon_eligible=True,
                missing_regime_filters=(),
            )

    def test_eligibility_matrix_requires_iterable_tokens_not_raw_string(self):
        with self.assertRaises(TypeError):
            family_eligibility_matrix(available_prerequisites="ohlcv_m15")

        with self.assertRaises(TypeError):
            family_eligibility_matrix(available_prerequisites=None)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            family_eligibility_matrix(
                available_prerequisites={"ohlcv_m15", "spread_bid_ask"},
                required_regime_filters="spread_max_pips",
            )

    def test_eligibility_matrix_can_apply_horizon_and_regime_filter_constraints(self):
        matrix = family_eligibility_matrix(
            available_prerequisites={
                "ohlcv_m15",
                "spread_bid_ask",
                "iana_timezone_rules",
            },
            target_horizon_bars=70,
            required_regime_filters={"spread_max_pips"},
        )
        by_id = {item.contract_id: item for item in matrix}

        self.assertFalse(by_id["S04"].eligible)
        self.assertFalse(by_id["S04"].horizon_eligible)  # S04 max horizon is 40
        self.assertEqual(by_id["S04"].missing_regime_filters, ())

        self.assertFalse(by_id["S05"].eligible)
        self.assertEqual(by_id["S05"].missing_regime_filters, ("spread_max_pips",))
        self.assertTrue(by_id["S05"].horizon_eligible)

        self.assertTrue(by_id["S02"].eligible)
        self.assertEqual(by_id["S02"].missing_regime_filters, ())

        with self.assertRaises(ValueError):
            family_eligibility_matrix(
                available_prerequisites={"ohlcv_m15", "spread_bid_ask"},
                target_horizon_bars=0,
            )

    def test_default_registry_remains_compatible_with_validated_guard(self):
        self.assertEqual(default_strategy_family_registry(), validated_strategy_family_registry())

    def test_redundancy_groups_return_only_overlaps_by_default(self):
        groups = family_redundancy_groups()
        self.assertEqual(
            groups,
            (
                FamilyRedundancyGroup(
                    epic_family_id=1,
                    epic_family_name="EMA / trend-following",
                    contract_ids=("S01", "S05"),
                ),
                FamilyRedundancyGroup(
                    epic_family_id=13,
                    epic_family_name="Macro-surprise",
                    contract_ids=("S12", "S13"),
                ),
            ),
        )

    def test_redundancy_groups_can_include_singletons_for_full_epic_coverage(self):
        groups = family_redundancy_groups(include_singletons=True)
        self.assertEqual(len(groups), 13)
        by_epic = {item.epic_family_id: item for item in groups}

        self.assertEqual(by_epic[2].contract_ids, ("S02",))
        self.assertEqual(by_epic[3].contract_ids, ("S04",))
        self.assertEqual(by_epic[11].contract_ids, ("S10",))
        self.assertEqual(by_epic[13].contract_ids, ("S12", "S13"))


if __name__ == "__main__":
    unittest.main()
