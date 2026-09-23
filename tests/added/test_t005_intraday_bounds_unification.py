"""Regression checks for shared conservative timestamp bounds in T005 flows."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from trading_lab.fundamentals import EconomicRelease, TimePoint, TimestampPrecision, release_as_of
from trading_lab.fundamentals import schema as fundamentals_schema


UTC = timezone.utc
BASE = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def _release(*, scheduled_precision=TimestampPrecision.MINUTE) -> EconomicRelease:
    return EconomicRelease(
        release_id="uk-gdp-2026q2",
        indicator="GDP",
        jurisdiction="UK",
        event_period="2026-Q2",
        scheduled_at=TimePoint(BASE, scheduled_precision),
        published_at=TimePoint(BASE + timedelta(minutes=1), TimestampPrecision.MINUTE),
        observed_at=TimePoint(BASE + timedelta(minutes=2), TimestampPrecision.MINUTE),
        available_at=TimePoint(BASE + timedelta(minutes=3), TimestampPrecision.MINUTE),
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


class T005SharedBoundsUnificationTests(unittest.TestCase):
    def test_releases_as_of_routes_availability_cutoff_through_shared_bounds(self):
        row = _release()
        with patch.object(
            fundamentals_schema,
            "_conservative_bounds",
            wraps=fundamentals_schema._conservative_bounds,
        ) as bounds_spy:
            found = release_as_of(
                [row],
                BASE + timedelta(minutes=5),
                jurisdiction="UK",
                indicator="GDP",
                event_period="2026-Q2",
            )

        self.assertIs(found, row)
        called_points = [call.args[0] for call in bounds_spy.call_args_list]
        self.assertIn(row.available_at, called_points)

    def test_intraday_same_day_precision_routes_overlap_check_through_shared_bounds(self):
        row = _release(scheduled_precision=TimestampPrecision.DAY)
        with patch.object(
            fundamentals_schema,
            "_conservative_bounds",
            wraps=fundamentals_schema._conservative_bounds,
        ) as bounds_spy:
            with self.assertRaises(fundamentals_schema.IntradayPrecisionError):
                fundamentals_schema.validate_intraday_same_day_precision(
                    row,
                    BASE + timedelta(minutes=5),
                )

        called_points = [call.args[0] for call in bounds_spy.call_args_list]
        self.assertIn(row.scheduled_at, called_points)


if __name__ == "__main__":
    unittest.main()
