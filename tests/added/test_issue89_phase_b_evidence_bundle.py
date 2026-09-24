"""Issue #89 Phase B tournament evidence bundle acceptance tests."""

import unittest

from trading_lab.strategies import default_strategy_family_registry
from trading_lab.tournament import (
    CoreLeagueCandidateFeedAdapter,
    CoreLeagueEvaluationHarness,
    IntraFamilyLeagueHarness,
    InterFamilyChampionshipHarness,
    PhaseBEvidenceBundleHarness,
    PhaseBEvidenceError,
    SelectorAblationHarness,
    SelectorCalibrationHarness,
    SelectorInputContractHarness,
)


class Issue89PhaseBEvidenceBundleTests(unittest.TestCase):
    def _build_stage_artifacts(self):
        available_prerequisites = {
            prerequisite: True
            for definition in default_strategy_family_registry()
            for prerequisite in definition.data_prerequisites
        }
        intra = IntraFamilyLeagueHarness().evaluate(
            available_prerequisites=available_prerequisites,
            variant_scores={
                "S01": {"S01-V01": 9.0},
                "S02": {"S02-V01": 8.0},
                "S03": {"S03-V01": 7.0},
            },
        )
        championship = InterFamilyChampionshipHarness().evaluate(
            intra_family_result=intra,
            champion_slots=1,
            runner_up_slots=2,
        )
        selector_input = SelectorInputContractHarness().build(championship_result=championship)
        candidate_feed = CoreLeagueCandidateFeedAdapter().build(selector_input=selector_input)
        core = CoreLeagueEvaluationHarness().evaluate(candidate_feed=candidate_feed)
        calibration = SelectorCalibrationHarness().calibrate(core_league_artifact=core)
        ablation = SelectorAblationHarness().compare(calibration_artifact=calibration)
        return intra, championship, selector_input, candidate_feed, core, calibration, ablation

    def test_bundle_is_reproducible_and_references_required_issue_chain(self):
        intra, championship, selector_input, candidate_feed, core, calibration, ablation = (
            self._build_stage_artifacts()
        )

        harness = PhaseBEvidenceBundleHarness()
        first = harness.build(
            strategy_registry=default_strategy_family_registry(),
            intra_family_result=intra,
            championship_result=championship,
            selector_input=selector_input,
            candidate_feed=candidate_feed,
            core_league_artifact=core,
            selector_calibration_artifact=calibration,
            selector_ablation_artifact=ablation,
        )
        second = harness.build(
            strategy_registry=default_strategy_family_registry(),
            intra_family_result=intra,
            championship_result=championship,
            selector_input=selector_input,
            candidate_feed=candidate_feed,
            core_league_artifact=core,
            selector_calibration_artifact=calibration,
            selector_ablation_artifact=ablation,
        )

        self.assertEqual(first, second)
        self.assertEqual(first.schema_version, "phase-b-evidence-bundle.v1")
        self.assertEqual(first.parent_epic, "#38")
        self.assertEqual(
            tuple(item.issue_ref for item in first.stage_refs),
            ("#76", "#78", "#80", "#82", "#83", "#84", "#86", "#87"),
        )

    def test_rejects_malformed_input_schema_with_machine_readable_reason(self):
        intra, championship, selector_input, candidate_feed, core, calibration, ablation = (
            self._build_stage_artifacts()
        )

        bad_core = core.to_dict()
        bad_core["schema_version"] = "core-league-evaluation.v0"

        with self.assertRaises(PhaseBEvidenceError) as ctx:
            PhaseBEvidenceBundleHarness().build(
                strategy_registry=default_strategy_family_registry(),
                intra_family_result=intra,
                championship_result=championship,
                selector_input=selector_input,
                candidate_feed=candidate_feed,
                core_league_artifact=bad_core,
                selector_calibration_artifact=calibration,
                selector_ablation_artifact=ablation,
            )

        self.assertIn("UNSUPPORTED_CORE_LEAGUE_SCHEMA", ctx.exception.reason_codes)

    def test_acceptance_metrics_pass_wait_shape_and_counter_alignment(self):
        intra, championship, selector_input, candidate_feed, core, calibration, ablation = (
            self._build_stage_artifacts()
        )

        bundle = PhaseBEvidenceBundleHarness().build(
            strategy_registry=default_strategy_family_registry(),
            intra_family_result=intra,
            championship_result=championship,
            selector_input=selector_input,
            candidate_feed=candidate_feed,
            core_league_artifact=core,
            selector_calibration_artifact=calibration,
            selector_ablation_artifact=ablation,
        )

        metrics = bundle.acceptance_metrics
        self.assertIn("pass_wait_accounting", metrics)
        self.assertIn("invariant_checks", metrics)
        self.assertIn("reproducibility_fingerprint", metrics)

        accounting = metrics["pass_wait_accounting"]
        self.assertIn("core_league", accounting)
        self.assertIn("selector_calibration", accounting)
        self.assertIn("selector_ablation_modes", accounting)

        checks = metrics["invariant_checks"]
        self.assertTrue(checks["counter_alignment"])
        self.assertIn("row_shape", checks)
        self.assertGreater(checks["row_shape"]["core_rows"], 0)


if __name__ == "__main__":
    unittest.main()
