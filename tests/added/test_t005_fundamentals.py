"""Acceptance tests for T005 point-in-time fundamentals."""
import unittest
from datetime import datetime, timedelta, timezone

from trading_lab.fundamentals import (
    EconomicRelease,
    IntradayPrecisionError,
    PITValidationError,
    TimePoint,
    TimestampPrecision,
    collect_release_pit_issues,
    VerificationStatus,
    default_source_registry,
    parse_release_payload,
    release_as_of,
    releases_as_of,
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
        pre_release_forecast_observed_at=(
            TimePoint(BASE - timedelta(minutes=30), TimestampPrecision.MINUTE)
            if forecast is not None
            else None
        ),
        pre_release_forecast_source_id=("licensed_forecast_provider" if forecast is not None else None),
        pre_release_forecast_source_version=("forecast-v1" if forecast is not None else None),
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

    def test_surprise_rejects_legacy_invalid_forecast_provenance_with_ingest_codes(self):
        row = release()
        object.__setattr__(row, "pre_release_forecast_observed_at", None)

        with self.assertRaises(PITValidationError) as ctx:
            row.surprise()

        self.assertEqual(
            [issue.code for issue in ctx.exception.issues],
            ["PIT_FORECAST_OBSERVED_AT_REQUIRED"],
        )

    def test_surprise_soft_fail_returns_none_for_legacy_invalid_forecast_provenance(self):
        row = release()
        object.__setattr__(row, "pre_release_forecast_observed_at", None)
        self.assertIsNone(row.surprise(soft_fail_on_pit_error=True))

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
            pre_release_forecast_observed_at=TimePoint(BASE - timedelta(minutes=30), TimestampPrecision.MINUTE),
            pre_release_forecast_source_id="licensed_forecast_provider",
            pre_release_forecast_source_version="forecast-v1",
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

    def test_hour_precision_availability_is_not_selected_before_conservative_upper_bound(self):
        row = EconomicRelease(
            release_id="uk-gdp-hour-available",
            indicator="GDP",
            jurisdiction="UK",
            event_period="2026-Q2",
            scheduled_at=TimePoint(BASE, TimestampPrecision.MINUTE),
            published_at=TimePoint(BASE, TimestampPrecision.MINUTE),
            observed_at=TimePoint(BASE, TimestampPrecision.MINUTE),
            available_at=TimePoint(BASE, TimestampPrecision.HOUR),
            first_actual=4.0,
            pre_release_forecast=4.1,
            pre_release_forecast_observed_at=TimePoint(BASE - timedelta(minutes=30), TimestampPrecision.MINUTE),
            pre_release_forecast_source_id="licensed_forecast_provider",
            pre_release_forecast_source_version="forecast-v1",
            previous_as_known=3.7,
            revision=None,
            source_id="ons",
            source_version="sample-v0",
            revision_seq=0,
        )
        found = release_as_of(
            [row],
            BASE + timedelta(minutes=59),
            jurisdiction="UK",
            indicator="GDP",
            event_period="2026-Q2",
        )
        self.assertIsNone(found)

    def test_hour_precision_availability_exact_upper_bound_is_selected_deterministically(self):
        row = EconomicRelease(
            release_id="uk-gdp-hour-available",
            indicator="GDP",
            jurisdiction="UK",
            event_period="2026-Q2",
            scheduled_at=TimePoint(BASE, TimestampPrecision.MINUTE),
            published_at=TimePoint(BASE, TimestampPrecision.MINUTE),
            observed_at=TimePoint(BASE, TimestampPrecision.MINUTE),
            available_at=TimePoint(BASE, TimestampPrecision.HOUR),
            first_actual=4.0,
            pre_release_forecast=4.1,
            pre_release_forecast_observed_at=TimePoint(BASE - timedelta(minutes=30), TimestampPrecision.MINUTE),
            pre_release_forecast_source_id="licensed_forecast_provider",
            pre_release_forecast_source_version="forecast-v1",
            previous_as_known=3.7,
            revision=None,
            source_id="ons",
            source_version="sample-v0",
            revision_seq=0,
        )
        found = release_as_of(
            [row],
            BASE + timedelta(hours=1),
            jurisdiction="UK",
            indicator="GDP",
            event_period="2026-Q2",
        )
        self.assertIs(found, row)

    def test_releases_as_of_uses_conservative_availability_order_deterministically(self):
        coarse = EconomicRelease(
            release_id="uk-gdp-2026q2",
            indicator="GDP",
            jurisdiction="UK",
            event_period="2026-Q2",
            scheduled_at=TimePoint(BASE, TimestampPrecision.MINUTE),
            published_at=TimePoint(BASE, TimestampPrecision.MINUTE),
            observed_at=TimePoint(BASE, TimestampPrecision.MINUTE),
            available_at=TimePoint(BASE, TimestampPrecision.HOUR),
            first_actual=4.0,
            pre_release_forecast=4.1,
            pre_release_forecast_observed_at=TimePoint(BASE - timedelta(minutes=30), TimestampPrecision.MINUTE),
            pre_release_forecast_source_id="licensed_forecast_provider",
            pre_release_forecast_source_version="forecast-v1",
            previous_as_known=3.7,
            revision=None,
            source_id="ons",
            source_version="sample-v1",
            revision_seq=0,
        )
        finer = EconomicRelease(
            release_id="uk-gdp-2026q2",
            indicator="GDP",
            jurisdiction="UK",
            event_period="2026-Q2",
            scheduled_at=TimePoint(BASE, TimestampPrecision.MINUTE),
            published_at=TimePoint(BASE, TimestampPrecision.MINUTE),
            observed_at=TimePoint(BASE + timedelta(minutes=1), TimestampPrecision.MINUTE),
            available_at=TimePoint(BASE + timedelta(minutes=30), TimestampPrecision.MINUTE),
            first_actual=4.0,
            pre_release_forecast=4.1,
            pre_release_forecast_observed_at=TimePoint(BASE - timedelta(minutes=30), TimestampPrecision.MINUTE),
            pre_release_forecast_source_id="licensed_forecast_provider",
            pre_release_forecast_source_version="forecast-v1",
            previous_as_known=3.7,
            revision=4.2,
            source_id="ons",
            source_version="sample-v2",
            revision_seq=0,
        )

        selected_forward = releases_as_of([coarse, finer], BASE + timedelta(hours=2))
        selected_reverse = releases_as_of([finer, coarse], BASE + timedelta(hours=2))

        self.assertIs(selected_forward[coarse.key], coarse)
        self.assertIs(selected_reverse[coarse.key], coarse)

    def test_releases_as_of_relaxed_intraday_requires_explicit_override_reason(self):
        row = release()
        with self.assertRaises(PITValidationError) as ctx:
            releases_as_of(
                [row],
                BASE + timedelta(minutes=10),
                intraday_same_day=False,
            )
        self.assertEqual(
            [issue.code for issue in ctx.exception.issues],
            ["PIT_INTRADAY_OVERRIDE_REASON_REQUIRED"],
        )
        self.assertEqual(
            ctx.exception.issues[0].message,
            "intraday_same_day=False requires non-empty intraday_override_reason",
        )

    def test_releases_as_of_relaxed_intraday_accepts_explicit_override_reason(self):
        row = release()
        selected = releases_as_of(
            [row],
            BASE + timedelta(minutes=10),
            intraday_same_day=False,
            intraday_override_reason="historical backfill replay",
        )
        self.assertIs(selected[row.key], row)

    def test_releases_as_of_relaxed_intraday_soft_fallback_enforces_strict_policy(self):
        row = release(scheduled_precision=TimestampPrecision.DAY)
        with self.assertRaises(IntradayPrecisionError):
            releases_as_of(
                [row],
                BASE + timedelta(minutes=10),
                intraday_same_day=False,
                soft_fail_intraday_override=True,
            )

    def test_release_as_of_relaxed_intraday_accepts_explicit_override_reason(self):
        row = release()
        found = release_as_of(
            [row],
            BASE + timedelta(minutes=10),
            jurisdiction="UK",
            indicator="GDP",
            event_period="2026-Q2",
            intraday_same_day=False,
            intraday_override_reason="historical backfill replay",
        )
        self.assertIs(found, row)

    def test_release_as_of_relaxed_intraday_requires_explicit_override_reason(self):
        row = release()
        with self.assertRaises(PITValidationError) as ctx:
            release_as_of(
                [row],
                BASE + timedelta(minutes=10),
                jurisdiction="UK",
                indicator="GDP",
                event_period="2026-Q2",
                intraday_same_day=False,
            )
        self.assertEqual(
            [issue.code for issue in ctx.exception.issues],
            ["PIT_INTRADAY_OVERRIDE_REASON_REQUIRED"],
        )

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
            pre_release_forecast_observed_at=None,
            pre_release_forecast_source_id=None,
            pre_release_forecast_source_version=None,
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
                pre_release_forecast_observed_at=TimePoint(BASE - timedelta(minutes=30), TimestampPrecision.MINUTE),
                pre_release_forecast_source_id="licensed_forecast_provider",
                pre_release_forecast_source_version="forecast-v1",
                previous_as_known=3.7,
                revision=None,
                source_id="ons",
                source_version="sample-v0",
            )

    def test_forecast_value_requires_explicit_observed_at_and_provenance(self):
        with self.assertRaises(ValueError):
            EconomicRelease(
                release_id="missing-forecast-metadata",
                indicator="CPI",
                jurisdiction="UK",
                event_period="2026-08",
                scheduled_at=tp(0),
                published_at=tp(1),
                observed_at=tp(2),
                available_at=tp(3),
                first_actual=4.0,
                pre_release_forecast=3.9,
                pre_release_forecast_observed_at=None,
                pre_release_forecast_source_id=None,
                pre_release_forecast_source_version=None,
                previous_as_known=3.8,
                revision=None,
                source_id="ons",
                source_version="sample-v0",
            )

    def test_forecast_source_id_must_exist_in_registry(self):
        with self.assertRaisesRegex(
            ValueError,
            "pre_release_forecast_source_id unknown_forecast_source is not in source registry",
        ):
            EconomicRelease(
                release_id="unknown-forecast-source",
                indicator="CPI",
                jurisdiction="UK",
                event_period="2026-08",
                scheduled_at=tp(0),
                published_at=tp(1),
                observed_at=tp(2),
                available_at=tp(3),
                first_actual=4.0,
                pre_release_forecast=3.9,
                pre_release_forecast_observed_at=TimePoint(BASE - timedelta(minutes=30), TimestampPrecision.MINUTE),
                pre_release_forecast_source_id="unknown_forecast_source",
                pre_release_forecast_source_version="forecast-v1",
                previous_as_known=3.8,
                revision=None,
                source_id="ons",
                source_version="sample-v0",
            )

    def test_forecast_source_must_be_forecast_capable(self):
        with self.assertRaisesRegex(
            ValueError,
            "pre_release_forecast_source_id forex_factory is not forecast-capable",
        ):
            EconomicRelease(
                release_id="non-forecast-source",
                indicator="CPI",
                jurisdiction="UK",
                event_period="2026-08",
                scheduled_at=tp(0),
                published_at=tp(1),
                observed_at=tp(2),
                available_at=tp(3),
                first_actual=4.0,
                pre_release_forecast=3.9,
                pre_release_forecast_observed_at=TimePoint(BASE - timedelta(minutes=30), TimestampPrecision.MINUTE),
                pre_release_forecast_source_id="forex_factory",
                pre_release_forecast_source_version="forecast-v1",
                previous_as_known=3.8,
                revision=None,
                source_id="ons",
                source_version="sample-v0",
            )

    def test_forecast_observed_precision_hour_is_rejected_for_same_day_intraday(self):
        row = release()
        row_with_hour_precision = EconomicRelease(
            release_id=row.release_id,
            indicator=row.indicator,
            jurisdiction=row.jurisdiction,
            event_period=row.event_period,
            scheduled_at=row.scheduled_at,
            published_at=row.published_at,
            observed_at=row.observed_at,
            available_at=row.available_at,
            first_actual=row.first_actual,
            pre_release_forecast=row.pre_release_forecast,
            pre_release_forecast_observed_at=TimePoint(BASE, TimestampPrecision.HOUR),
            pre_release_forecast_source_id=row.pre_release_forecast_source_id,
            pre_release_forecast_source_version=row.pre_release_forecast_source_version,
            previous_as_known=row.previous_as_known,
            revision=row.revision,
            source_id=row.source_id,
            source_version=row.source_version,
            revision_seq=row.revision_seq,
        )
        with self.assertRaises(IntradayPrecisionError):
            release_as_of(
                [row_with_hour_precision],
                BASE + timedelta(minutes=10),
                jurisdiction="UK",
                indicator="GDP",
                event_period="2026-Q2",
            )

    def test_forecast_hour_precision_crossing_midnight_is_rejected_conservatively(self):
        decision = datetime(2026, 8, 8, 0, 10, tzinfo=UTC)
        row = EconomicRelease(
            release_id="uk-cpi-2026-08",
            indicator="CPI",
            jurisdiction="UK",
            event_period="2026-08",
            scheduled_at=TimePoint(datetime(2026, 8, 8, 0, 0, tzinfo=UTC), TimestampPrecision.MINUTE),
            published_at=None,
            observed_at=TimePoint(datetime(2026, 8, 8, 0, 4, tzinfo=UTC), TimestampPrecision.MINUTE),
            available_at=TimePoint(datetime(2026, 8, 8, 0, 5, tzinfo=UTC), TimestampPrecision.MINUTE),
            first_actual=4.0,
            pre_release_forecast=3.9,
            pre_release_forecast_observed_at=TimePoint(
                datetime(2026, 8, 7, 23, 30, tzinfo=UTC),
                TimestampPrecision.HOUR,
            ),
            pre_release_forecast_source_id="licensed_forecast_provider",
            pre_release_forecast_source_version="forecast-v1",
            previous_as_known=3.8,
            revision=None,
            source_id="ons",
            source_version="sample-v0",
        )
        with self.assertRaises(IntradayPrecisionError):
            release_as_of(
                [row],
                decision,
                jurisdiction="UK",
                indicator="CPI",
                event_period="2026-08",
            )

    def test_forecast_hour_precision_exact_midnight_boundary_is_deterministically_allowed(self):
        decision = datetime(2026, 8, 8, 0, 10, tzinfo=UTC)
        row = EconomicRelease(
            release_id="uk-cpi-2026-08",
            indicator="CPI",
            jurisdiction="UK",
            event_period="2026-08",
            scheduled_at=TimePoint(datetime(2026, 8, 8, 0, 0, tzinfo=UTC), TimestampPrecision.MINUTE),
            published_at=None,
            observed_at=TimePoint(datetime(2026, 8, 8, 0, 4, tzinfo=UTC), TimestampPrecision.MINUTE),
            available_at=TimePoint(datetime(2026, 8, 8, 0, 5, tzinfo=UTC), TimestampPrecision.MINUTE),
            first_actual=4.0,
            pre_release_forecast=3.9,
            pre_release_forecast_observed_at=TimePoint(
                datetime(2026, 8, 7, 23, 0, tzinfo=UTC),
                TimestampPrecision.HOUR,
            ),
            pre_release_forecast_source_id="licensed_forecast_provider",
            pre_release_forecast_source_version="forecast-v1",
            previous_as_known=3.8,
            revision=None,
            source_id="ons",
            source_version="sample-v0",
        )
        found = release_as_of(
            [row],
            decision,
            jurisdiction="UK",
            indicator="CPI",
            event_period="2026-08",
        )
        self.assertIs(found, row)

    def test_forecast_hour_precision_just_before_midnight_boundary_is_allowed(self):
        decision = datetime(2026, 8, 8, 0, 10, tzinfo=UTC)
        row = EconomicRelease(
            release_id="uk-cpi-2026-08",
            indicator="CPI",
            jurisdiction="UK",
            event_period="2026-08",
            scheduled_at=TimePoint(datetime(2026, 8, 8, 0, 0, tzinfo=UTC), TimestampPrecision.MINUTE),
            published_at=None,
            observed_at=TimePoint(datetime(2026, 8, 8, 0, 4, tzinfo=UTC), TimestampPrecision.MINUTE),
            available_at=TimePoint(datetime(2026, 8, 8, 0, 5, tzinfo=UTC), TimestampPrecision.MINUTE),
            first_actual=4.0,
            pre_release_forecast=3.9,
            pre_release_forecast_observed_at=TimePoint(
                datetime(2026, 8, 7, 22, 59, tzinfo=UTC),
                TimestampPrecision.HOUR,
            ),
            pre_release_forecast_source_id="licensed_forecast_provider",
            pre_release_forecast_source_version="forecast-v1",
            previous_as_known=3.8,
            revision=None,
            source_id="ons",
            source_version="sample-v0",
        )
        found = release_as_of(
            [row],
            decision,
            jurisdiction="UK",
            indicator="CPI",
            event_period="2026-08",
        )
        self.assertIs(found, row)

    def test_forecast_hour_precision_just_after_midnight_boundary_is_rejected(self):
        decision = datetime(2026, 8, 8, 0, 10, tzinfo=UTC)
        row = EconomicRelease(
            release_id="uk-cpi-2026-08",
            indicator="CPI",
            jurisdiction="UK",
            event_period="2026-08",
            scheduled_at=TimePoint(datetime(2026, 8, 8, 0, 0, tzinfo=UTC), TimestampPrecision.MINUTE),
            published_at=None,
            observed_at=TimePoint(datetime(2026, 8, 8, 0, 4, tzinfo=UTC), TimestampPrecision.MINUTE),
            available_at=TimePoint(datetime(2026, 8, 8, 0, 5, tzinfo=UTC), TimestampPrecision.MINUTE),
            first_actual=4.0,
            pre_release_forecast=3.9,
            pre_release_forecast_observed_at=TimePoint(
                datetime(2026, 8, 7, 23, 1, tzinfo=UTC),
                TimestampPrecision.HOUR,
            ),
            pre_release_forecast_source_id="licensed_forecast_provider",
            pre_release_forecast_source_version="forecast-v1",
            previous_as_known=3.8,
            revision=None,
            source_id="ons",
            source_version="sample-v0",
        )
        with self.assertRaises(IntradayPrecisionError):
            release_as_of(
                [row],
                decision,
                jurisdiction="UK",
                indicator="CPI",
                event_period="2026-08",
            )

    def test_forecast_unknown_precision_same_day_is_rejected_for_intraday_use(self):
        row = release()
        row_with_unknown_precision = EconomicRelease(
            release_id=row.release_id,
            indicator=row.indicator,
            jurisdiction=row.jurisdiction,
            event_period=row.event_period,
            scheduled_at=row.scheduled_at,
            published_at=row.published_at,
            observed_at=row.observed_at,
            available_at=row.available_at,
            first_actual=row.first_actual,
            pre_release_forecast=row.pre_release_forecast,
            pre_release_forecast_observed_at=TimePoint(BASE, TimestampPrecision.UNKNOWN),
            pre_release_forecast_source_id=row.pre_release_forecast_source_id,
            pre_release_forecast_source_version=row.pre_release_forecast_source_version,
            previous_as_known=row.previous_as_known,
            revision=row.revision,
            source_id=row.source_id,
            source_version=row.source_version,
            revision_seq=row.revision_seq,
        )
        with self.assertRaises(IntradayPrecisionError):
            release_as_of(
                [row_with_unknown_precision],
                BASE + timedelta(minutes=10),
                jurisdiction="UK",
                indicator="GDP",
                event_period="2026-Q2",
            )

    def test_downstream_release_as_of_rejects_same_missing_forecast_metadata_as_ingest(self):
        expected = "pre_release_forecast_observed_at is required when pre_release_forecast is set"
        with self.assertRaisesRegex(ValueError, expected):
            EconomicRelease(
                release_id="missing-forecast-observed-at",
                indicator="CPI",
                jurisdiction="UK",
                event_period="2026-08",
                scheduled_at=tp(0),
                published_at=tp(1),
                observed_at=tp(2),
                available_at=tp(3),
                first_actual=4.0,
                pre_release_forecast=3.9,
                pre_release_forecast_observed_at=None,
                pre_release_forecast_source_id="licensed_forecast_provider",
                pre_release_forecast_source_version="forecast-v1",
                previous_as_known=3.8,
                revision=None,
                source_id="ons",
                source_version="sample-v0",
            )

        legacy = release()
        object.__setattr__(legacy, "pre_release_forecast_observed_at", None)
        with self.assertRaisesRegex(ValueError, expected):
            release_as_of(
                [legacy],
                BASE + timedelta(minutes=10),
                jurisdiction="UK",
                indicator="GDP",
                event_period="2026-Q2",
            )

    def test_parse_release_payload_accepts_explicit_timepoints_and_provenance(self):
        row = parse_release_payload(
            {
                "release_id": "uk-gdp-2026q2",
                "indicator": "GDP",
                "jurisdiction": "UK",
                "event_period": "2026-Q2",
                "scheduled_at": TimePoint(BASE, TimestampPrecision.MINUTE),
                "published_at": tp(1),
                "observed_at": tp(2),
                "available_at": tp(3),
                "first_actual": 4.0,
                "pre_release_forecast": 3.9,
                "pre_release_forecast_observed_at": TimePoint(
                    BASE - timedelta(minutes=30),
                    TimestampPrecision.MINUTE,
                ),
                "pre_release_forecast_source_id": "licensed_forecast_provider",
                "pre_release_forecast_source_version": "forecast-v1",
                "previous_as_known": 3.8,
                "revision": None,
                "source_id": "ons",
                "source_version": "sample-v0",
                "revision_seq": 0,
            }
        )
        self.assertIsInstance(row, EconomicRelease)
        self.assertEqual(row.pre_release_forecast, 3.9)

    def test_parse_release_payload_returns_deterministic_sorted_issue_codes(self):
        payload = {
            "release_id": "uk-gdp-2026q2",
            "indicator": "GDP",
            "jurisdiction": "UK",
            "event_period": "2026-Q2",
            "scheduled_at": TimePoint(BASE, TimestampPrecision.MINUTE),
            "observed_at": tp(2),
            "available_at": tp(3),
            "source_id": "ons",
            "source_version": "sample-v0",
            "pre_release_forecast": 3.9,
            "pre_release_forecast_source_id": "unknown_forecast_source",
            "pre_release_forecast_source_version": "forecast-v1",
        }
        with self.assertRaises(PITValidationError) as ctx:
            parse_release_payload(payload)
        got_codes = [item.code for item in ctx.exception.issues]
        self.assertEqual(got_codes, sorted(got_codes))
        self.assertIn("PIT_FORECAST_OBSERVED_AT_REQUIRED", got_codes)
        self.assertIn("PIT_FORECAST_SOURCE_NOT_REGISTERED", got_codes)

    def test_parse_release_payload_rejects_invalid_required_timepoint_types_deterministically(self):
        payload = {
            "release_id": "uk-gdp-2026q2",
            "indicator": "GDP",
            "jurisdiction": "UK",
            "event_period": "2026-Q2",
            "scheduled_at": "2026-08-07T12:00:00Z",
            "observed_at": tp(2),
            "available_at": "2026-08-07T12:03:00Z",
            "source_id": "ons",
            "source_version": "sample-v0",
        }
        with self.assertRaises(PITValidationError) as ctx:
            parse_release_payload(payload)

        got = [(item.code, item.field) for item in ctx.exception.issues]
        self.assertEqual(
            got,
            [
                ("PARSER_TIMEPOINT_TYPE_INVALID", "available_at"),
                ("PARSER_TIMEPOINT_TYPE_INVALID", "scheduled_at"),
            ],
        )

    def test_parse_release_payload_reports_timepoint_type_errors_deterministically(self):
        payload = {
            "release_id": "uk-gdp-2026q2",
            "indicator": "GDP",
            "jurisdiction": "UK",
            "event_period": "2026-Q2",
            "scheduled_at": TimePoint(BASE, TimestampPrecision.MINUTE),
            "observed_at": "2026-08-07T12:02:00Z",
            "available_at": tp(3),
            "source_id": "ons",
            "source_version": "sample-v0",
            "pre_release_forecast": 3.9,
            "pre_release_forecast_observed_at": "2026-08-07T11:30:00Z",
            "pre_release_forecast_source_id": "licensed_forecast_provider",
            "pre_release_forecast_source_version": "forecast-v1",
        }
        with self.assertRaises(PITValidationError) as ctx:
            parse_release_payload(payload)
        got_codes = [item.code for item in ctx.exception.issues]
        self.assertEqual(got_codes, sorted(got_codes))
        self.assertIn("PARSER_TIMEPOINT_TYPE_INVALID", got_codes)
        got_fields = [item.field for item in ctx.exception.issues]
        self.assertIn("observed_at", got_fields)
        self.assertIn("pre_release_forecast_observed_at", got_fields)

    def test_parse_release_payload_does_not_infer_forecast_validity_from_field_name_only(self):
        payload = {
            "release_id": "uk-gdp-2026q2",
            "indicator": "GDP",
            "jurisdiction": "UK",
            "event_period": "2026-Q2",
            "scheduled_at": TimePoint(BASE, TimestampPrecision.MINUTE),
            "published_at": tp(1),
            "observed_at": tp(2),
            "available_at": tp(3),
            "first_actual": 4.0,
            "pre_release_forecast": 3.9,
            "source_id": "ons",
            "source_version": "sample-v0",
            "legacy_pre_release_forecast_hint": "exists",
        }
        with self.assertRaises(PITValidationError) as ctx:
            parse_release_payload(payload)
        messages = [item.message for item in ctx.exception.issues]
        self.assertIn(
            "pre_release_forecast_observed_at is required when pre_release_forecast is set",
            messages,
        )
        self.assertIn(
            "pre_release_forecast_source_id is required when pre_release_forecast is set",
            messages,
        )
        self.assertIn(
            "pre_release_forecast_source_version is required when pre_release_forecast is set",
            messages,
        )

    def test_model_validation_rejects_missing_observed_at_with_pit_code(self):
        with self.assertRaises(PITValidationError) as ctx:
            EconomicRelease(
                release_id="model-missing-observed-at",
                indicator="GDP",
                jurisdiction="UK",
                event_period="2026-Q2",
                scheduled_at=tp(0),
                published_at=tp(1),
                observed_at=None,
                available_at=tp(3),
                first_actual=4.0,
                pre_release_forecast=3.9,
                pre_release_forecast_observed_at=TimePoint(BASE - timedelta(minutes=30), TimestampPrecision.MINUTE),
                pre_release_forecast_source_id="licensed_forecast_provider",
                pre_release_forecast_source_version="forecast-v1",
                previous_as_known=3.8,
                revision=None,
                source_id="ons",
                source_version="sample-v0",
            )
        self.assertEqual(
            [issue.code for issue in ctx.exception.issues],
            ["PIT_OBSERVED_AT_REQUIRED"],
        )
        self.assertEqual(ctx.exception.issues[0].field, "observed_at")
        self.assertEqual(ctx.exception.issues[0].message, "observed_at is required")

    def test_model_validation_keeps_deterministic_issue_order_for_multiple_forecast_failures(self):
        with self.assertRaises(PITValidationError) as ctx:
            EconomicRelease(
                release_id="model-forecast-failures",
                indicator="CPI",
                jurisdiction="UK",
                event_period="2026-08",
                scheduled_at=tp(0),
                published_at=tp(1),
                observed_at=tp(2),
                available_at=tp(3),
                first_actual=4.0,
                pre_release_forecast=3.9,
                pre_release_forecast_observed_at=None,
                pre_release_forecast_source_id="unknown_forecast_source",
                pre_release_forecast_source_version=None,
                previous_as_known=3.8,
                revision=None,
                source_id="ons",
                source_version="sample-v0",
            )
        self.assertEqual(
            [issue.code for issue in ctx.exception.issues],
            [
                "PIT_FORECAST_OBSERVED_AT_REQUIRED",
                "PIT_FORECAST_SOURCE_VERSION_REQUIRED",
                "PIT_FORECAST_SOURCE_NOT_REGISTERED",
            ],
        )


class T005PITValidationLayeredDeterminismTests(unittest.TestCase):
    def _base_payload(self) -> dict[str, object]:
        return {
            "release_id": "uk-gdp-2026q2",
            "indicator": "GDP",
            "jurisdiction": "UK",
            "event_period": "2026-Q2",
            "scheduled_at": TimePoint(BASE, TimestampPrecision.MINUTE),
            "published_at": tp(1),
            "observed_at": tp(2),
            "available_at": tp(3),
            "first_actual": 4.0,
            "pre_release_forecast": 3.9,
            "pre_release_forecast_observed_at": TimePoint(
                BASE - timedelta(minutes=30),
                TimestampPrecision.MINUTE,
            ),
            "pre_release_forecast_source_id": "licensed_forecast_provider",
            "pre_release_forecast_source_version": "forecast-v1",
            "previous_as_known": 3.8,
            "revision": None,
            "source_id": "ons",
            "source_version": "sample-v0",
            "revision_seq": 0,
        }

    def _schema_issues(self, mutator):
        row = release()
        mutator(row)
        return [
            (issue.code, issue.field, issue.message)
            for issue in collect_release_pit_issues(row)
        ]

    def test_schema_layer_missing_observed_at_exact_reason_payload(self):
        got = self._schema_issues(lambda row: object.__setattr__(row, "observed_at", None))
        self.assertEqual(
            got,
            [
                (
                    "PIT_OBSERVED_AT_REQUIRED",
                    "observed_at",
                    "observed_at is required",
                )
            ],
        )

    def test_schema_layer_invalid_observed_at_and_invalid_provenance_is_deterministic(self):
        def mutate(row):
            object.__setattr__(row, "observed_at", "2026-08-07T12:02:00Z")
            object.__setattr__(row, "pre_release_forecast_source_id", "unknown_forecast_source")

        got = self._schema_issues(mutate)
        self.assertEqual(
            got,
            [
                (
                    "PIT_OBSERVED_AT_TYPE_INVALID",
                    "observed_at",
                    "observed_at must be provided as TimePoint",
                ),
                (
                    "PIT_FORECAST_SOURCE_NOT_REGISTERED",
                    "pre_release_forecast_source_id",
                    "pre_release_forecast_source_id unknown_forecast_source is not in source registry",
                ),
            ],
        )

    def test_schema_layer_both_missing_and_multiple_failures_have_stable_order(self):
        def mutate(row):
            object.__setattr__(row, "observed_at", None)
            object.__setattr__(row, "pre_release_forecast_observed_at", None)
            object.__setattr__(row, "pre_release_forecast_source_version", None)
            object.__setattr__(row, "pre_release_forecast_source_id", "unknown_forecast_source")

        got = self._schema_issues(mutate)
        self.assertEqual(
            got,
            [
                (
                    "PIT_OBSERVED_AT_REQUIRED",
                    "observed_at",
                    "observed_at is required",
                ),
                (
                    "PIT_FORECAST_OBSERVED_AT_REQUIRED",
                    "pre_release_forecast_observed_at",
                    "pre_release_forecast_observed_at is required when pre_release_forecast is set",
                ),
                (
                    "PIT_FORECAST_SOURCE_VERSION_REQUIRED",
                    "pre_release_forecast_source_version",
                    "pre_release_forecast_source_version is required when pre_release_forecast is set",
                ),
                (
                    "PIT_FORECAST_SOURCE_NOT_REGISTERED",
                    "pre_release_forecast_source_id",
                    "pre_release_forecast_source_id unknown_forecast_source is not in source registry",
                ),
            ],
        )

    def test_model_layer_missing_observed_at_and_missing_forecast_provenance(self):
        with self.assertRaises(PITValidationError) as ctx:
            EconomicRelease(
                release_id="model-missing-observed-and-provenance",
                indicator="GDP",
                jurisdiction="UK",
                event_period="2026-Q2",
                scheduled_at=tp(0),
                published_at=tp(1),
                observed_at=None,
                available_at=tp(3),
                first_actual=4.0,
                pre_release_forecast=3.9,
                pre_release_forecast_observed_at=None,
                pre_release_forecast_source_id=None,
                pre_release_forecast_source_version=None,
                previous_as_known=3.8,
                revision=None,
                source_id="ons",
                source_version="sample-v0",
            )
        self.assertEqual(
            [(i.code, i.field, i.message) for i in ctx.exception.issues],
            [
                (
                    "PIT_OBSERVED_AT_REQUIRED",
                    "observed_at",
                    "observed_at is required",
                ),
                (
                    "PIT_FORECAST_OBSERVED_AT_REQUIRED",
                    "pre_release_forecast_observed_at",
                    "pre_release_forecast_observed_at is required when pre_release_forecast is set",
                ),
                (
                    "PIT_FORECAST_SOURCE_ID_REQUIRED",
                    "pre_release_forecast_source_id",
                    "pre_release_forecast_source_id is required when pre_release_forecast is set",
                ),
                (
                    "PIT_FORECAST_SOURCE_VERSION_REQUIRED",
                    "pre_release_forecast_source_version",
                    "pre_release_forecast_source_version is required when pre_release_forecast is set",
                ),
            ],
        )

    def test_parser_layer_missing_observed_at_uses_parser_required_reason(self):
        payload = self._base_payload()
        payload.pop("observed_at")
        with self.assertRaises(PITValidationError) as ctx:
            parse_release_payload(payload)
        self.assertEqual(
            [(i.code, i.field, i.message) for i in ctx.exception.issues],
            [
                (
                    "PARSER_REQUIRED_FIELD_MISSING",
                    "observed_at",
                    "observed_at is required",
                )
            ],
        )

    def test_parser_layer_missing_forecast_provenance_and_name_hint_regression(self):
        payload = self._base_payload()
        payload["legacy_pre_release_forecast_hint"] = "exists"
        payload["pre_release_forecast_observed_at"] = None
        payload["pre_release_forecast_source_id"] = None
        payload["pre_release_forecast_source_version"] = None

        with self.assertRaises(PITValidationError) as ctx:
            parse_release_payload(payload)

        self.assertEqual(
            [(i.code, i.field, i.message) for i in ctx.exception.issues],
            [
                (
                    "PIT_FORECAST_OBSERVED_AT_REQUIRED",
                    "pre_release_forecast_observed_at",
                    "pre_release_forecast_observed_at is required when pre_release_forecast is set",
                ),
                (
                    "PIT_FORECAST_SOURCE_ID_REQUIRED",
                    "pre_release_forecast_source_id",
                    "pre_release_forecast_source_id is required when pre_release_forecast is set",
                ),
                (
                    "PIT_FORECAST_SOURCE_VERSION_REQUIRED",
                    "pre_release_forecast_source_version",
                    "pre_release_forecast_source_version is required when pre_release_forecast is set",
                ),
            ],
        )

    def test_parser_layer_multiple_simultaneous_timepoint_failures_are_sorted(self):
        payload = self._base_payload()
        payload["scheduled_at"] = "2026-08-07T12:00:00Z"
        payload["available_at"] = "2026-08-07T12:03:00Z"
        payload["observed_at"] = "2026-08-07T12:02:00Z"

        with self.assertRaises(PITValidationError) as ctx:
            parse_release_payload(payload)

        self.assertEqual(
            [(i.code, i.field, i.message) for i in ctx.exception.issues],
            [
                (
                    "PARSER_TIMEPOINT_TYPE_INVALID",
                    "available_at",
                    "available_at must be provided as TimePoint",
                ),
                (
                    "PARSER_TIMEPOINT_TYPE_INVALID",
                    "observed_at",
                    "observed_at must be provided as TimePoint",
                ),
                (
                    "PARSER_TIMEPOINT_TYPE_INVALID",
                    "scheduled_at",
                    "scheduled_at must be provided as TimePoint",
                ),
            ],
        )

    def test_cross_layer_missing_forecast_provenance_semantics_align(self):
        def mutate_schema(row):
            object.__setattr__(row, "pre_release_forecast_observed_at", None)
            object.__setattr__(row, "pre_release_forecast_source_id", None)
            object.__setattr__(row, "pre_release_forecast_source_version", None)

        schema_got = self._schema_issues(mutate_schema)

        with self.assertRaises(PITValidationError) as model_ctx:
            EconomicRelease(
                release_id="cross-layer-missing-forecast-provenance",
                indicator="GDP",
                jurisdiction="UK",
                event_period="2026-Q2",
                scheduled_at=tp(0),
                published_at=tp(1),
                observed_at=tp(2),
                available_at=tp(3),
                first_actual=4.0,
                pre_release_forecast=3.9,
                pre_release_forecast_observed_at=None,
                pre_release_forecast_source_id=None,
                pre_release_forecast_source_version=None,
                previous_as_known=3.8,
                revision=None,
                source_id="ons",
                source_version="sample-v0",
            )

        payload = self._base_payload()
        payload["pre_release_forecast_observed_at"] = None
        payload["pre_release_forecast_source_id"] = None
        payload["pre_release_forecast_source_version"] = None
        with self.assertRaises(PITValidationError) as parser_ctx:
            parse_release_payload(payload)

        expected = [
            (
                "PIT_FORECAST_OBSERVED_AT_REQUIRED",
                "pre_release_forecast_observed_at",
                "pre_release_forecast_observed_at is required when pre_release_forecast is set",
            ),
            (
                "PIT_FORECAST_SOURCE_ID_REQUIRED",
                "pre_release_forecast_source_id",
                "pre_release_forecast_source_id is required when pre_release_forecast is set",
            ),
            (
                "PIT_FORECAST_SOURCE_VERSION_REQUIRED",
                "pre_release_forecast_source_version",
                "pre_release_forecast_source_version is required when pre_release_forecast is set",
            ),
        ]

        self.assertEqual(
            [item for item in schema_got if item[0].startswith("PIT_FORECAST_")],
            expected,
        )
        self.assertEqual(
            [(i.code, i.field, i.message) for i in model_ctx.exception.issues],
            expected,
        )
        self.assertEqual(
            [(i.code, i.field, i.message) for i in parser_ctx.exception.issues],
            expected,
        )


if __name__ == "__main__":
    unittest.main()
