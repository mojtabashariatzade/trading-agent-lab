# T005 forecast PIT acceptance matrix (implementation-facing)

Scope: point-in-time validation for forecast-bearing `EconomicRelease` rows.
This matrix is normative for schema validation and intraday as-of selection tests.

## 1) Required field formats and normalization

- `observed_at`: required `TimePoint` with timezone-aware UTC datetime.
  - Rejection message when naive timestamp is used anywhere in a `TimePoint`: `Timezone-aware timestamp required`
- `pre_release_forecast`: optional finite float (`None` allowed).
  - Rejection for NaN/inf: `pre_release_forecast must be finite or None`
- `pre_release_forecast_observed_at`: `TimePoint | None`
- `pre_release_forecast_source_id`: `str | None`, trimmed, must be non-blank when provided.
  - Blank rejection: `pre_release_forecast_source_id cannot be blank`
- `pre_release_forecast_source_version`: `str | None`, trimmed, must be non-blank when provided.
  - Blank rejection: `pre_release_forecast_source_version cannot be blank`
- Forecast source must be registry-backed and forecast-capable (`SourceKind.LICENSED_FORECAST`).

## 2) Acceptance/rejection matrix

| Case | `pre_release_forecast` | `pre_release_forecast_observed_at` | `pre_release_forecast_source_id` | `pre_release_forecast_source_version` | `observed_at` | Provenance/source rule | Chronology/precision rule | Outcome | Exact rejection message |
|---|---|---|---|---|---|---|---|---|---|
| A1 | `None` | `None` | `None` | `None` | present, UTC-aware | n/a | `published_at <= observed_at <= available_at` (when `published_at` exists) | ACCEPT | n/a |
| A2 | finite | present, UTC-aware | non-empty | non-empty | present, UTC-aware | source id exists and source kind is `LICENSED_FORECAST` | `forecast_observed <= published_at` (if published exists) and `forecast_observed <= available_at` | ACCEPT | n/a |
| R1 | finite | `None` | any | any | any | n/a | n/a | REJECT | `pre_release_forecast_observed_at is required when pre_release_forecast is set` |
| R2 | finite | present | `None` | any | any | n/a | n/a | REJECT | `pre_release_forecast_source_id is required when pre_release_forecast is set` |
| R3 | finite | present | non-empty | `None` | any | n/a | n/a | REJECT | `pre_release_forecast_source_version is required when pre_release_forecast is set` |
| R4 | `None` | present and/or source fields present | any | any | any | metadata must be null-coupled when forecast is null | n/a | REJECT | `pre_release_forecast metadata cannot be set when pre_release_forecast is None` |
| R5 | finite | present | blank/whitespace | any | any | non-blank requirement | n/a | REJECT | `pre_release_forecast_source_id cannot be blank` |
| R6 | finite | present | non-empty | blank/whitespace | any | non-blank requirement | n/a | REJECT | `pre_release_forecast_source_version cannot be blank` |
| R7 | finite | present | unknown id | non-empty | any | source id must exist in registry | n/a | REJECT | `pre_release_forecast_source_id <id> is not in source registry` |
| R8 | finite | present | known non-forecast source (e.g. `forex_factory`) | non-empty | any | source kind must be forecast-capable | n/a | REJECT | `pre_release_forecast_source_id <id> is not forecast-capable` |
| R9 | any | any | any | any | before `published_at` | n/a | violates publication->observation ordering | REJECT | `observed_at cannot precede published_at` |
| R10 | any | any | any | any | after `available_at` | n/a | violates observation->availability ordering | REJECT | `available_at cannot precede observed_at` |
| R11 | finite | after `published_at` | valid | valid | valid | provenance otherwise valid | forecast observed too late vs publication | REJECT | `pre_release_forecast_observed_at cannot be after published_at` |
| R12 | finite | after `available_at` | valid | valid | valid | provenance otherwise valid | forecast observed too late vs availability | REJECT | `pre_release_forecast_observed_at cannot be after available_at` |
| R13 | finite | same-day intraday with precision `HOUR`/`DAY`/`UNKNOWN` | valid | valid | valid | n/a | conservative precision rule | REJECT (`IntradayPrecisionError`) | `pre_release_forecast_observed_at precision <PRECISION> is not valid for same-day intraday use` |
| R14 | any | any | any | any | same-day intraday and any of `scheduled_at`/`published_at`/`observed_at`/`available_at` has precision `DAY`/`UNKNOWN` | n/a | intraday precision insufficient | REJECT (`IntradayPrecisionError`) | `<field_name> precision <PRECISION> is not valid for same-day intraday use` |

## 3) Notes for implementation and tests

1. Do not infer PIT validity from field names alone. Names like `pre_release_forecast` express intent, not proof of observation time, source lineage, or causal availability.
2. PIT acceptance MUST be determined from explicit timestamps + explicit provenance fields + source-registry kind checks.
3. Use UTC-aware timestamps only; timezone-naive datetimes are always invalid.
4. For same-day intraday decisions, use precision-interval overlap semantics (half-open intervals) to enforce conservative rejection, including hour values crossing midnight into decision day.
5. When recording expected failures in tests, assert exact messages above (including dynamic `<id>`, `<field_name>`, `<PRECISION>` substitutions).