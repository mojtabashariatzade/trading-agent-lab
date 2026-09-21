"""Acceptance tests for T005 point-in-time fundamentals."""
import unittest
from datetime import datetime, timedelta, timezone

from trading_lab.fundamentals import (
    EconomicRelease,
    IntradayPrecisionError,
    TimePoint,
    TimestampPrecision,
    VerificationStatus,
    default_source_registry,
    release_as_of,
)


UTC = timezone.utc
BASE = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def tp(minutes, precision=TimestampPrecision.MINUTE):
    return TimePoint(BASE + timedelta(minutes=minutes), precision)


def release(
    *,
    available_minute=3,
    revision=None,
    revision_seq=0,
    forecast=4.1,
    scheduled_precision=TimestampPrecision.MINUTE,
    observed_precision=TimestampPrecision.MINUTE,
    available_precision=TimestampPrecision.MINUTE,
):
    return EconomicRelease(
        release_id="uk-gdp-2026q2",
        indicator="GDP",
        jurisdiction="UK",
        event_period="2026-Q2",
        scheduled_at=TimePoint(BASE, scheduled_precision),
        published_at=tp(1),
        observed_at=TimePoint(BASE + timedelta(minutes=2), observed_precision),
        available_at=TimePoint(BASE + timedelta(minutes=available_minute), available_precision),
        first_actual=4.0,
        pre_release_forecast=forecast,
        previous_as_known=3.7,
        revision=revision,
        source_id="ons",
        source_version=f"sample-v{revision_seq}",
        revision_seq=revision_seq,
    )


class T005FundamentalsTests(unittest.TestCase):
    def test_release_keeps_all_times_and_values_separate(self):
        row = release(revision=4.2, revision_seq=1)
        self.assertNotEqual(row.scheduled_at.value, row.published_at.value)
        self.assertNotEqual(row.published_at.value, row.observed_at.value)
        self.assertNotEqual(row.observed_at.value, row.available_at.value)
        self.assertEqual(row.event_period, "2026-Q2")
        self.assertEqual(row.first_actual, 4.0)
        self.assertEqual(row.pre_release_forecast, 4.1)
        self.assertEqual(row.previous_as_known, 3.7)
        self.assertEqual(row.revision, 4.2)

    def test_missing_forecast_stays_none_and_surprise_is_unknown(self):
        row = release(forecast=None)
        self.assertIsNone(row.pre_release_forecast)
        self.assertIsNone(row.surprise())

    def test_surprise_uses_first_actual_not_revision(self):
        row = release(revision=4.8, revision_seq=1)
        self.assertAlmostEqual(row.surprise(), -0.1)
        self.assertEqual(row.first_actual, 4.0)
        self.assertEqual(row.revision, 4.8)

    def test_as_of_join_hides_future_revision(self):
        first = release(available_minute=3, revision=None, revision_seq=0)
        revised = EconomicRelease(
            release_id=first.release_id,
            indicator=first.indicator,
            jurisdiction=first.jurisdiction,
            event_period=first.event_period,
            scheduled_at=first.scheduled_at,
            published_at=first.published_at,
            observed_at=tp(20),
            available_at=tp(21),
            first_actual=4.0,
            pre_release_forecast=4.1,
            previous_as_known=3.7,
            revision=4.6,
            source_id="ons",
            source_version="sample-v1",
            revision_seq=1,
        )

        before = release_as_of(
            [first, revised],
            BASE + timedelta(minutes=10),
            jurisdiction="UK",
            indicator="GDP",
            event_period="2026-Q2",
        )
        after = release_as_of(
            [first, revised],
            BASE + timedelta(minutes=30),
            jurisdiction="UK",
            indicator="GDP",
            event_period="2026-Q2",
        )
        self.assertIs(before, first)
        self.assertIs(after, revised)
        self.assertEqual(before.first_actual, 4.0)
        self.assertIsNone(before.revision)
        self.assertEqual(after.first_actual, 4.0)
        self.assertEqual(after.revision, 4.6)

    def test_not_available_yet_returns_none(self):
        row = release(available_minute=10)
        found = release_as_of(
            [row],
            BASE + timedelta(minutes=5),
            jurisdiction="UK",
            indicator="GDP",
            event_period="2026-Q2",
        )
        self.assertIsNone(found)

    def test_daily_same_day_timestamp_is_rejected_for_intraday_use(self):
        row = release(scheduled_precision=TimestampPrecision.DAY)
        with self.assertRaises(IntradayPrecisionError):
            release_as_of(
                [row],
                BASE + timedelta(minutes=10),
                jurisdiction="UK",
                indicator="GDP",
                event_period="2026-Q2",
            )

    def test_unknown_same_day_availability_is_rejected_for_intraday_use(self):
        row = release(available_precision=TimestampPrecision.UNKNOWN)
        with self.assertRaises(IntradayPrecisionError):
            release_as_of(
                [row],
                BASE + timedelta(minutes=10),
                jurisdiction="UK",
                indicator="GDP",
                event_period="2026-Q2",
            )

    def test_prior_day_daily_timestamp_can_be_used_next_day(self):
        prior = BASE - timedelta(days=1)
        row = EconomicRelease(
            release_id="prior-event",
            indicator="CPI",
            jurisdiction="JP",
            event_period="2026-07",
            scheduled_at=TimePoint(prior, TimestampPrecision.DAY),
            published_at=None,
            observed_at=TimePoint(prior, TimestampPrecision.DAY),
            available_at=TimePoint(prior, TimestampPrecision.DAY),
            first_actual=2.2,
            pre_release_forecast=None,
            previous_as_known=2.1,
            revision=None,
            source_id="statistics_bureau_japan",
            source_version="sample-v0",
        )
        found = release_as_of(
            [row],
            BASE + timedelta(minutes=30),
            jurisdiction="JP",
            indicator="CPI",
            event_period="2026-07",
        )
        self.assertIs(found, row)
        self.assertIsNone(found.pre_release_forecast)

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            TimePoint(datetime(2026, 8, 7, 12, 0), TimestampPrecision.MINUTE)

    def test_source_registry_contains_required_sources_all_unverified(self):
        registry = default_source_registry()
        expected = {
            "forex_factory",
            "ons",
            "boe",
            "boj",
            "statistics_bureau_japan",
            "esri_japan",
            "mof_japan",
            "federal_reserve",
            "bls",
            "bea",
            "alfred",
            "licensed_forecast_provider",
        }
        self.assertEqual(set(registry.ids()), expected)
        for entry in registry.entries:
            self.assertEqual(entry.history_status, VerificationStatus.UNVERIFIED)
            self.assertEqual(entry.license_status, VerificationStatus.UNVERIFIED)
            self.assertEqual(entry.coverage_status, VerificationStatus.UNVERIFIED)

    def test_time_ordering_cannot_claim_data_available_before_observed(self):
        with self.assertRaises(ValueError):
            EconomicRelease(
                release_id="bad-order",
                indicator="GDP",
                jurisdiction="UK",
                event_period="2026-Q2",
                scheduled_at=tp(0),
                published_at=tp(1),
                observed_at=tp(4),
                available_at=tp(3),
                first_actual=4.0,
                pre_release_forecast=4.1,
                previous_as_known=3.7,
                revision=None,
                source_id="ons",
                source_version="sample-v0",
            )


if __name__ == "__main__":
    unittest.main()
