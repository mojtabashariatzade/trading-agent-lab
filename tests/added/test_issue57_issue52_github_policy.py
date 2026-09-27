"""Tests for process policy validators bound to issues #57 and #52."""

import unittest

from trading_lab.research.github_policy import (
    evaluate_blocker_metadata_policy,
    evaluate_epic_creation_policy,
)


class Issue57Issue52PolicyTests(unittest.TestCase):
    def test_epic_creation_policy_passes_when_all_required_fields_exist(self):
        body = """
        Why existing epics cannot absorb the scope:
        Existing epics do not include this execution-kernel migration.

        Dependency map:
        blocked-by: #120
        blocks: #130, #131

        Owner: @kian

        Acceptance criteria:
        - deterministic replay checksum is stable
        - CI test suite passes

        Delivery impact:
        adds one day, reduces regression risk.
        """

        result = evaluate_epic_creation_policy(body)
        self.assertTrue(result.compliant)
        self.assertEqual(result.missing_requirements, ())

    def test_epic_creation_policy_fails_when_dependency_map_missing(self):
        body = """
        Why existing epics cannot absorb the scope: major architecture split.
        Owner: @kian
        Acceptance criteria: objective replay parity checks.
        Delivery impact: one-day delay, lower risk.
        """

        result = evaluate_epic_creation_policy(body)
        self.assertFalse(result.compliant)
        self.assertIn("DEPENDENCY_MAP_BLOCKED_BY_AND_BLOCKS", result.missing_requirements)

    def test_blocker_metadata_policy_passes_with_complete_fields(self):
        body = """
        Reason: missing upstream fixture package in protected environment.
        Owner: @negar
        Dependency: blocked-by #212
        Unblock condition: unblocked when fixture artifact is uploaded to release assets.
        """

        result = evaluate_blocker_metadata_policy(body)
        self.assertTrue(result.compliant)
        self.assertEqual(result.missing_requirements, ())

    def test_blocker_metadata_policy_fails_without_unblock_condition(self):
        body = """
        Reason: staging credential unavailable.
        Owner: @ops
        Dependency: blocked-by #400
        """

        result = evaluate_blocker_metadata_policy(body)
        self.assertFalse(result.compliant)
        self.assertIn("UNBLOCK_CONDITION", result.missing_requirements)


if __name__ == "__main__":
    unittest.main()
