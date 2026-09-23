"""Parity tests to keep ingest and downstream PIT validation behavior aligned."""

import unittest
from datetime import datetime, timedelta, timezone

from trading_lab.fundamentals import (
    EconomicRelease,
    PITValidationError,
    TimePoint,
    TimestampPrecision,
    parse_release_payload,
    release_as_of,
    releases_as_of,
    validate_release_pit_constraints,
)


UTC = timezone.utc
BASE = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def tp(minutes: int, precision: TimestampPrecision = TimestampPrecision.MINUTE) -> TimePoint:
    return TimePoint(BASE + timedelta(minutes=minutes), precision)


def base_payload() -> dict[str, object]:
    return {
        "release_id": "uk-gdp-2026q2",
        "indicator": "GDP",
        "jurisdiction": "UK",
        "event_period": "2026-Q2",
        "scheduled_at": tp(0),
        "published_at": tp(1),
        "observed_at": tp(2),
        "available_at": tp(3),
        "first_actual": 4.0,
        "pre_release_forecast": 4.1,
        "pre_release_forecast_observed_at": tp(-30),
        "pre_release_forecast_source_id": "licensed_forecast_provider",
        "pre_release_forecast_source_version": "forecast-v1",
        "previous_as_known": 3.7,
        "revision": None,
        "source_id": "ons",
        "source_version": "sample-v0",
        "revision_seq": 0,
    }


def payload_with(**overrides: object) -> dict[str, object]:
    row = base_payload()
    row.update(overrides)
    return row


def mutate_release(release: EconomicRelease, **overrides: object) -> EconomicRelease:
    for field, value in overrides.items():
        object.__setattr__(release, field, value)
    return release


class IngestDownstreamParityTests(unittest.TestCase):
    def assert_invalid_codes_match_across_stages(self, *, expected: list[str], overrides: dict[str, object]) -> None:
        ingest_payload = payload_with(**overrides)

        with self.assertRaises(PITValidationError) as ingest_ctx:
            parse_release_payload(ingest_payload)
        ingest_codes = [issue.code for issue in ingest_ctx.exception.issues]
        self.assertEqual(sorted(ingest_codes), sorted(expected))

        baseline = parse_release_payload(base_payload())
        mutated = mutate_release(baseline, **overrides)
        with self.assertRaises(PITValidationError) as downstream_ctx:
            validate_release_pit_constraints(mutated)
        downstream_codes = [issue.code for issue in downstream_ctx.exception.issues]
        self.assertEqual(sorted(downstream_codes), sorted(expected))
        self.assertEqual(sorted(downstream_codes), sorted(ingest_codes))

    def test_identical_valid_cases_are_accepted_by_ingest_and_downstream(self):
        valid_cases = [
            (
                "baseline fully specified payload",
                {},
            ),
            (
                "missing forecast remains unknown with no metadata",
                {
                    "pre_release_forecast": None,
                    "pre_release_forecast_observed_at": None,
                    "pre_release_forecast_source_id": None,
                    "pre_release_forecast_source_version": None,
                },
            ),
            (
                "published_at optional when omitted",
                {
                    "published_at": None,
                },
            ),
        ]

        for _, overrides in valid_cases:
            with self.subTest(overrides=overrides):
                parsed = parse_release_payload(payload_with(**overrides))
                validate_release_pit_constraints(parsed)

    def test_identical_invalid_cases_reject_with_same_reason_codes(self):
        invalid_cases = [
            (
                "forecast missing observed_at",
                {"pre_release_forecast_observed_at": None},
                ["PIT_FORECAST_OBSERVED_AT_REQUIRED"],
            ),
            (
                "forecast missing source id",
                {"pre_release_forecast_source_id": None},
                ["PIT_FORECAST_SOURCE_ID_REQUIRED"],
            ),
            (
                "forecast missing source version",
                {"pre_release_forecast_source_version": None},
                ["PIT_FORECAST_SOURCE_VERSION_REQUIRED"],
            ),
            (
                "forecast metadata present without forecast value",
                {"pre_release_forecast": None},
                ["PIT_FORECAST_METADATA_WITHOUT_FORECAST"],
            ),
            (
                "forecast observed after available",
                {"pre_release_forecast_observed_at": tp(4)},
                [
                    "PIT_FORECAST_OBSERVED_AFTER_AVAILABLE",
                    "PIT_FORECAST_OBSERVED_AFTER_PUBLISHED",
                ],
            ),
            (
                "available precedes observed (revision timing chronology)",
                {
                    "observed_at": tp(4),
                    "available_at": tp(3),
                },
                ["PIT_AVAILABLE_BEFORE_OBSERVED"],
            ),
            (
                "observed precedes published",
                {
                    "published_at": tp(2),
                    "observed_at": tp(1),
                },
                ["PIT_OBSERVED_BEFORE_PUBLISHED"],
            ),
            (
                "unknown forecast source",
                {"pre_release_forecast_source_id": "unknown_forecast_source"},
                ["PIT_FORECAST_SOURCE_NOT_REGISTERED"],
            ),
            (
                "forecast source not forecast-capable",
                {"pre_release_forecast_source_id": "forex_factory"},
                ["PIT_FORECAST_SOURCE_NOT_FORECAST_CAPABLE"],
            ),
        ]

        for _, overrides, expected_codes in invalid_cases:
            with self.subTest(overrides=overrides, expected_codes=expected_codes):
                self.assert_invalid_codes_match_across_stages(
                    expected=expected_codes,
                    overrides=overrides,
                )

    def test_revision_timing_is_deterministic_in_downstream_selection(self):
        initial = parse_release_payload(base_payload())
        revision_payload = payload_with(
            observed_at=tp(20),
            available_at=tp(21),
            revision=4.6,
            revision_seq=1,
            source_version="sample-v1",
        )
        revised = parse_release_payload(revision_payload)

        before_revision = release_as_of(
            [initial, revised],
            BASE + timedelta(minutes=10),
            jurisdiction="UK",
            indicator="GDP",
            event_period="2026-Q2",
        )
        after_revision = release_as_of(
            [initial, revised],
            BASE + timedelta(minutes=30),
            jurisdiction="UK",
            indicator="GDP",
            event_period="2026-Q2",
        )

        self.assertIs(before_revision, initial)
        self.assertIs(after_revision, revised)

        selected_forward = releases_as_of([initial, revised], BASE + timedelta(minutes=30))
        selected_reverse = releases_as_of([revised, initial], BASE + timedelta(minutes=30))
        self.assertIs(selected_forward[initial.key], revised)
        self.assertIs(selected_reverse[initial.key], revised)


if __name__ == "__main__":
    unittest.main()
