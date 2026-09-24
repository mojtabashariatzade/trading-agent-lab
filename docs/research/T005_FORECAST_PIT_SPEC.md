# T005 forecast point-in-time (PIT) provenance specification

This specification defines when forecast-bearing fundamental records are eligible for intraday use. It is normative for ingest validators, schema checks and as-of selection logic.

## 1) `observed_at` semantics (mandatory)

`observed_at` is the collector-observation timestamp, not a label inferred from field names.

- `published_at`: source/provider publication timestamp, when exposed by the source.
- `observed_at`: first UTC timestamp when our collector actually observed that specific version of the record.
- `available_at`: earliest UTC time our research pipeline may use the record.

Required ordering:
- if `published_at` exists: `published_at <= observed_at`
- always: `observed_at <= available_at`

Rejection rules:
- missing `observed_at`
- timezone-naive timestamps
- ordering violations above

## 2) Forecast provenance fields and accepted values (mandatory when forecast exists)

If `pre_release_forecast` is set (non-null), all fields below are required:

- `pre_release_forecast_observed_at` (UTC `TimePoint`): when the forecast value was observed by our collector.
- `pre_release_forecast_source_id` (non-empty string): source registry id for that forecast value.
- `pre_release_forecast_source_version` (non-empty string): provider snapshot/version/build identifier used by collector.

Accepted-source policy:
- `pre_release_forecast_source_id` must exist in `default_source_registry().ids()`.
- For forecast fields, the source kind must be `LICENSED_FORECAST` (currently `licensed_forecast_provider`) unless a new forecast-capable source is explicitly added to the registry with review.

Causality constraints for forecast metadata:
- if `published_at` exists: `pre_release_forecast_observed_at <= published_at`
- always: `pre_release_forecast_observed_at <= available_at`

Null-coupling rule:
- if `pre_release_forecast` is null, all three forecast-metadata fields above must also be null.

## 3) Invalid/rejected conditions

Reject/flag a record as PIT-invalid when any of these occur:

1. `pre_release_forecast` present but any required forecast-metadata field missing/blank.
2. `pre_release_forecast` null but forecast metadata provided.
3. `observed_at` missing or invalid.
4. `pre_release_forecast_source_id` not in source registry or not forecast-capable.
5. `pre_release_forecast_observed_at` after `published_at` (if present) or after `available_at`.
6. Any required timestamp is timezone-naive or has impossible chronology.

## 4) Field names are not PIT evidence

Names such as `pre_release_forecast` indicate intended meaning only. They do not prove:
- when the value was observed,
- which source/version supplied it,
- whether it was causally available before decision time.

Therefore PIT validity must be decided only from timestamps + provenance constraints, never by regex/name-pattern checks.

## 5) Conservative intraday precision policy

For same-day intraday decisions, enforce conservative precision checks:

- reject `scheduled_at`, `published_at`, `observed_at`, or `available_at` when precision is `DAY` or `UNKNOWN`.
- reject `pre_release_forecast_observed_at` when precision is `HOUR`, `DAY`, or `UNKNOWN` on the same decision day.
- prior-day day-level timestamps may be accepted next day because intraday ordering ambiguity has elapsed.

Implementation note for deterministic boundary handling:
- evaluate same-day eligibility using precision intervals and UTC day overlap, not raw date equality only.
- use half-open intervals `[lower_bound, upper_bound)` so exact midnight boundaries are deterministic.
- for `DAY`/`UNKNOWN`, normalize to UTC day buckets before overlap checks.
- for `HOUR` forecast-observed timestamps, widen by one hour; if that interval overlaps the decision day, treat as same-day intraday and reject.

## 6) Concrete examples

Valid (forecast PIT-eligible):

```json
{
  "release_id": "uk-cpi-2026-08",
  "source_id": "ons",
  "source_version": "ons-api-2026-09-01T07:00Z",
  "published_at": "2026-09-16T07:00:00Z",
  "observed_at": "2026-09-16T07:01:12Z",
  "available_at": "2026-09-16T07:02:00Z",
  "pre_release_forecast": 2.3,
  "pre_release_forecast_observed_at": "2026-09-15T18:30:00Z",
  "pre_release_forecast_source_id": "licensed_forecast_provider",
  "pre_release_forecast_source_version": "consensus-snap-2026-09-15T18:30Z"
}
```

Invalid A (name present, metadata missing):

```json
{
  "pre_release_forecast": 2.3,
  "pre_release_forecast_observed_at": null,
  "pre_release_forecast_source_id": null,
  "pre_release_forecast_source_version": null
}
```

Invalid B (provenance source not accepted for forecast):

```json
{
  "pre_release_forecast": 2.3,
  "pre_release_forecast_observed_at": "2026-09-15T18:30:00Z",
  "pre_release_forecast_source_id": "forex_factory",
  "pre_release_forecast_source_version": "calendar-page-123"
}
```

Invalid C (forecast observed after publication):

```json
{
  "published_at": "2026-09-16T07:00:00Z",
  "pre_release_forecast_observed_at": "2026-09-16T08:00:00Z"
}
```

Invalid D (same-day intraday precision too coarse):

```json
{
  "decision_time": "2026-09-16T09:15:00Z",
  "pre_release_forecast_observed_at": {
    "value": "2026-09-16T08:00:00Z",
    "precision": "HOUR"
  }
}
```

## 7) Compatibility and migration-safe handling

- Downstream consumers must run the same PIT constraints used at ingest before using forecast-bearing fields.
- If legacy/backfilled rows violate these constraints, fail fast with the same rejection message as ingest instead of silently inferring validity from field names.
- Migration-safe rollout: quarantine or repair PIT-invalid legacy rows (set forecast + metadata coherently, or set all forecast fields to null) before re-enabling downstream selection on that dataset.

Detailed rollout, rollback, and monitoring guidance is documented in:
- `docs/research/T005_PIT_COMPATIBILITY_AND_MIGRATION.md`
