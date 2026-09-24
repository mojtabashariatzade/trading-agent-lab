"""Acceptance tests for Issue #76 strategy-family registry."""

import unittest

from trading_lab.strategies import default_strategy_family_registry


class Issue76FamilyRegistryTests(unittest.TestCase):
    def test_registry_contains_all_contract_families_once(self):
        registry = default_strategy_family_registry()
        ids = [item.contract_id for item in registry]
        self.assertEqual(len(registry), 15)
        self.assertEqual(len(set(ids)), 15)
        self.assertEqual(ids, [f"S{i:02d}" for i in range(1, 16)])

    def test_epic_taxonomy_mapping_is_explicit_and_valid(self):
        registry = default_strategy_family_registry()
        epic_labels = {
            1: "EMA / trend-following",
            2: "Breakout / Donchian",
            3: "Session-range breakout",
            4: "Mean reversion / Bollinger re-entry",
            5: "Momentum / ROC",
            6: "RSI-style exhaustion/reversal",
            7: "Volatility expansion/compression",
            8: "Price-action / candle-structure",
            9: "Support-resistance / swing structure",
            10: "Multi-timeframe trend/regime",
            11: "Currency-strength / cross-sectional FX",
            12: "Carry / rate-differential regime",
            13: "Macro-surprise",
            14: "Central-bank communication/text",
            15: "News/event-risk reaction",
        }
        for item in registry:
            self.assertEqual(item.epic_family_name, epic_labels[item.epic_family_id])
            self.assertIn(item.taxonomy_alignment, {"DIRECT", "RECONCILED"})
            if item.taxonomy_alignment == "RECONCILED":
                self.assertTrue(item.taxonomy_note.strip())

    def test_schema_bounds_and_data_prerequisites_are_bounded(self):
        registry = default_strategy_family_registry()
        for item in registry:
            self.assertGreaterEqual(item.variant_count_bounds[0], 1)
            self.assertGreaterEqual(item.variant_count_bounds[1], item.variant_count_bounds[0])
            self.assertGreaterEqual(item.horizon_bars[0], 1)
            self.assertGreaterEqual(item.horizon_bars[1], item.horizon_bars[0])
            self.assertTrue(item.parameter_bounds)
            for lower, upper in item.parameter_bounds.values():
                self.assertLessEqual(lower, upper)
            self.assertTrue(item.filters)
            self.assertTrue(item.data_prerequisites)

    def test_fundamental_families_require_point_in_time_sources(self):
        registry = {item.contract_id: item for item in default_strategy_family_registry()}

        self.assertIn("official_uk_releases_pti", registry["S12"].data_prerequisites)
        self.assertIn("official_jp_releases_pti", registry["S13"].data_prerequisites)
        self.assertIn("official_central_bank_text_pti", registry["S14"].data_prerequisites)
        self.assertIn("headline_archive_pti", registry["S15"].data_prerequisites)


if __name__ == "__main__":
    unittest.main()
