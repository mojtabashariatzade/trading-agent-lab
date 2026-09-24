"""Acceptance-style checks for the canonical strategy-family registry (Issue #38)."""

import unittest

from trading_lab.strategies.family_registry import (
    StrategyFamilyDefinition,
    validated_strategy_family_registry,
)


class T004FamilyRegistryTests(unittest.TestCase):
    def test_registry_contains_each_contract_id_exactly_once(self):
        registry = validated_strategy_family_registry()
        ids = [entry.contract_id for entry in registry]
        self.assertEqual(len(registry), 15)
        self.assertEqual(ids, [f"S{i:02d}" for i in range(1, 16)])

    def test_registry_entries_keep_required_selection_structure(self):
        registry = validated_strategy_family_registry()
        for entry in registry:
            self.assertGreaterEqual(entry.variant_count_bounds[0], 1)
            self.assertGreaterEqual(entry.variant_count_bounds[1], entry.variant_count_bounds[0])
            self.assertGreaterEqual(entry.horizon_bars[0], 1)
            self.assertGreaterEqual(entry.horizon_bars[1], entry.horizon_bars[0])
            self.assertTrue(entry.filters)
            self.assertTrue(entry.parameter_bounds)
            self.assertTrue(entry.data_prerequisites)

    def test_reconciled_taxonomy_entries_require_mapping_note(self):
        registry = validated_strategy_family_registry()
        reconciled = [entry for entry in registry if entry.taxonomy_alignment == "RECONCILED"]
        self.assertTrue(reconciled)
        for entry in reconciled:
            self.assertTrue(entry.taxonomy_note.strip())

    def test_contract_id_validation_enforces_s01_to_s15(self):
        with self.assertRaises(ValueError):
            StrategyFamilyDefinition(
                contract_id="S16",
                contract_name="Invalid",
                epic_family_id=1,
                epic_family_name="EMA / trend-following",
                taxonomy_alignment="DIRECT",
                taxonomy_note="",
                variant_count_bounds=(1, 1),
                parameter_bounds={"x": (1.0, 1.0)},
                filters=("f",),
                horizon_bars=(1, 1),
                data_prerequisites=("ohlcv_m15",),
            )

    def test_direct_taxonomy_alignment_rejects_non_empty_note(self):
        with self.assertRaises(ValueError):
            StrategyFamilyDefinition(
                contract_id="S01",
                contract_name="EMA trend",
                epic_family_id=1,
                epic_family_name="EMA / trend-following",
                taxonomy_alignment="DIRECT",
                taxonomy_note="should be empty for direct mapping",
                variant_count_bounds=(1, 2),
                parameter_bounds={"x": (1.0, 2.0)},
                filters=("f",),
                horizon_bars=(1, 2),
                data_prerequisites=("ohlcv_m15",),
            )


if __name__ == "__main__":
    unittest.main()
