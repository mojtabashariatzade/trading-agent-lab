"""Acceptance tests for Issue #38 family registry eligibility helpers."""

import unittest

from trading_lab.strategies import (
    FamilyEligibility,
    default_strategy_family_registry,
    family_definition_by_contract_id,
    family_eligibility_matrix,
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
        )
        self.assertEqual(item.missing_prerequisites, ("ohlcv_m15", "spread_bid_ask"))

        with self.assertRaises(ValueError):
            FamilyEligibility(
                contract_id="S01",
                eligible=True,
                missing_prerequisites=("ohlcv_m15",),
            )

    def test_default_registry_remains_compatible_with_validated_guard(self):
        self.assertEqual(default_strategy_family_registry(), validated_strategy_family_registry())


if __name__ == "__main__":
    unittest.main()
