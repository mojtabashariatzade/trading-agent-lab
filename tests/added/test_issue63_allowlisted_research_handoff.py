from datetime import datetime, timezone
import unittest

from trading_lab.research.routing import (
    ResearchExecutorCapability,
    ResearchKind,
    ResearchRequest,
    RouteState,
    build_read_only_handoff_record,
    decide_research_route,
)


class TestIssue63AllowlistedResearchHandoff(unittest.TestCase):
    def _request(self, kind: ResearchKind = ResearchKind.FUNDAMENTAL) -> ResearchRequest:
        return ResearchRequest(
            task_id="r-63-1",
            kind=kind,
            question="BoE calendar revision timings",
            requested_by="arman",
        )

    def test_supported_executor_routes_to_research_lane_only(self):
        decision = decide_research_route(
            self._request(ResearchKind.STRATEGY),
            ResearchExecutorCapability(
                executor_name="chatgpt-research",
                available=True,
                supported_kinds=(ResearchKind.STRATEGY, ResearchKind.FUNDAMENTAL),
            ),
        )

        self.assertEqual(decision.state, RouteState.DISPATCH)
        self.assertEqual(decision.route, "research_executor")
        self.assertFalse(decision.blocked)
        self.assertFalse(decision.coding_lane_allowed)

    def test_unavailable_executor_produces_explicit_blocker(self):
        decision = decide_research_route(
            self._request(),
            ResearchExecutorCapability(
                executor_name="chatgpt-research",
                available=False,
                supported_kinds=(ResearchKind.FUNDAMENTAL,),
            ),
        )

        self.assertEqual(decision.state, RouteState.BLOCKED)
        self.assertEqual(decision.route, "read_only_handoff")
        self.assertTrue(decision.blocked)
        self.assertIn("unavailable", decision.owner_visible_reason.lower())
        self.assertFalse(decision.coding_lane_allowed)

    def test_interrupted_launch_goes_to_read_only_handoff(self):
        decision = decide_research_route(
            self._request(ResearchKind.DATA),
            ResearchExecutorCapability(
                executor_name="chatgpt-research",
                available=True,
                supported_kinds=(ResearchKind.DATA,),
            ),
            launch_interrupted=True,
        )

        self.assertEqual(decision.state, RouteState.INTERRUPTED)
        self.assertEqual(decision.route, "read_only_handoff")
        self.assertTrue(decision.blocked)
        self.assertIn("interrupted", decision.owner_visible_reason.lower())
        self.assertFalse(decision.coding_lane_allowed)

    def test_status_reporting_truthfulness_in_handoff_record(self):
        decision = decide_research_route(
            self._request(ResearchKind.DATA),
            ResearchExecutorCapability(
                executor_name="chatgpt-research",
                available=True,
                supported_kinds=(ResearchKind.FUNDAMENTAL,),
            ),
        )
        captured = datetime(2026, 9, 24, 19, 55, tzinfo=timezone.utc)
        record = build_read_only_handoff_record(self._request(ResearchKind.DATA), decision, captured)

        self.assertEqual(record.schema, "trading-agent-lab.research-handoff.v1")
        self.assertEqual(record.route_state, RouteState.BLOCKED.value)
        self.assertEqual(record.reported_executor, "UNSUPPORTED_KIND")
        self.assertTrue(record.blocked)
        self.assertEqual(record.captured_at_utc, captured.isoformat())


if __name__ == "__main__":
    unittest.main()
