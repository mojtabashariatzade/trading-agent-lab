# T005 conservative PIT intraday precision bounding specification

Purpose: define one deterministic, implementation-ready bounding rule for intraday point-in-time (PIT) eligibility when timestamp precision and source certainty are limited.

Status: normative for all intraday forecast timestamp consumers (`releases_as_of`, `release_as_of`, PIT chronology checks, and any future consumer).

## 1) Canonical rule

Treat every `TimePoint(value, precision)` as a conservative half-open interval:
- `SECOND` -> `[value, value + 1s)`
- `MINUTE` -> `[value, value + 1m)`
- `HOUR` -> `[value, value + 1h)`
- `DAY` -> `[utc_day_start(value), utc_day_start(value) + 1d)`
- `UNKNOWN` -> same as `DAY` (UTC day bucket)

Normative assumptions:
1. All comparisons are UTC-aware and timezone-normalized before any logic.
2. Precision intervals are half-open (`[lower, upper)`), so exact upper-bound equality is deterministic.
3. For coarse precision, never infer availability at `value`; only infer guaranteed availability at `upper`.

## 2) Deterministic boundary behavior

### 2.1 As-of availability cutoff

Use `effective_available_at(point) = interval_upper(point)`.
A release is eligible at decision time `D` iff:
- `effective_available_at(available_at) <= D`

This yields deterministic outcomes:
- Exact boundary (`D == upper`) -> ELIGIBLE
- Just-before boundary (`D < upper`, even by 1 microsecond) -> INELIGIBLE
- Just-after boundary (`D > upper`) -> ELIGIBLE

### 2.2 Same-day overlap test (intraday precision gate)

Let decision UTC day be `[day_start, day_end)`.
`overlaps_decision_day(point, D)` is true iff:
- `interval_lower(point) < day_end` AND `interval_upper(point) > day_start`

This avoids date-string heuristics and handles midnight boundaries deterministically.

## 3) Intraday rejection policy (conservative)

When `intraday_same_day=True`:

1) Reject same-day imprecise structural timestamps:
- Fields: `scheduled_at`, `published_at`, `observed_at`, `available_at`
- Reject if `overlaps_decision_day(field, D)` and precision in `{DAY, UNKNOWN}`

2) Reject same-day coarse forecast-observed timestamps:
- Field: `pre_release_forecast_observed_at` (only when forecast exists)
- Reject if `overlaps_decision_day(pre_release_forecast_observed_at, D)` and precision in `{HOUR, DAY, UNKNOWN}`

3) Prior-day coarse timestamps are allowed when they do not overlap decision day.

## 4) Missing/ambiguous precision and source certainty

1. Missing or ambiguous precision:
- Treat missing/unspecified precision as `UNKNOWN` (conservative default).
- `UNKNOWN` uses UTC day bucket bounds and follows same rejection policy above.

2. Ambiguous forecast source certainty:
- If `pre_release_forecast` is present, require all forecast provenance fields:
  - `pre_release_forecast_observed_at`
  - `pre_release_forecast_source_id`
  - `pre_release_forecast_source_version`
- Reject if source id is unregistered or not forecast-capable.
- Reject chronology if forecast observed time can be after publication/availability under conservative bounds.

3. Null-coupling:
- If `pre_release_forecast` is null, all forecast provenance fields must be null.

Safe default principle: uncertainty never upgrades eligibility.

## 5) Timezone normalization assumptions

Normative:
- Inputs must be timezone-aware datetimes.
- Normalize all datetimes to UTC exactly once at `TimePoint` construction.
- Reject timezone-naive timestamps.
- All boundary/day calculations are in UTC only.

## 6) Decision table

| Case | Inputs | Rule | Outcome |
|---|---|---|---|
| C1 exact boundary | `D == upper(available_at)` | `upper <= D` | ACCEPT |
| C2 just-before boundary | `D < upper(available_at)` | `upper <= D` fails | REJECT |
| C3 just-after boundary | `D > upper(available_at)` | `upper <= D` | ACCEPT |
| C4 same-day DAY structural field | overlaps day and precision `DAY` | structural intraday reject set | REJECT (`IntradayPrecisionError`) |
| C5 same-day UNKNOWN structural field | overlaps day and precision `UNKNOWN` | structural intraday reject set | REJECT (`IntradayPrecisionError`) |
| C6 same-day HOUR forecast-observed | forecast exists, overlaps day, precision `HOUR` | forecast intraday reject set | REJECT (`IntradayPrecisionError`) |
| C7 forecast HOUR just before midnight, spills into day | upper crosses `day_start` | overlap test true | REJECT |
| C8 forecast HOUR ending exactly at day start | `upper == day_start` | overlap test false (half-open) | ALLOW (subject to other checks) |
| C9 missing precision | precision unavailable | coerce to `UNKNOWN` | conservative rule applies |
| C10 missing forecast source metadata | forecast set but metadata incomplete | PIT provenance required | REJECT (`PITValidationError`) |
| C11 unregistered/non-forecast source | source id invalid/capability mismatch | source certainty required | REJECT (`PITValidationError`) |
| C12 timezone-naive timestamp | any required timestamp naive | UTC-aware required | REJECT (`ValueError`/PIT parser error) |

## 7) Implementation pseudocode

```text
function precision_bounds(point):
    t = to_utc(point.value)
    switch point.precision:
      SECOND  -> return [t, t + 1s)
      MINUTE  -> return [t, t + 1m)
      HOUR    -> return [t, t + 1h)
      DAY     -> d = start_of_utc_day(t); return [d, d + 1d)
      UNKNOWN -> d = start_of_utc_day(t); return [d, d + 1d)

function effective_available_at(point):
    (_, upper) = precision_bounds(point)
    return upper

function overlaps_decision_day(point, decision_time_utc):
    day_start = start_of_utc_day(decision_time_utc)
    day_end = day_start + 1d
    (lower, upper) = precision_bounds(point)
    return (lower < day_end) and (upper > day_start)

function validate_intraday_same_day_precision(release, decision_time_utc):
    validate_release_pit_constraints(release)

    for field in [scheduled_at, published_at, observed_at, available_at]:
        if field exists and overlaps_decision_day(field, decision_time_utc):
            if field.precision in {DAY, UNKNOWN}:
                raise IntradayPrecisionError

    if release.pre_release_forecast exists:
        fp = release.pre_release_forecast_observed_at
        if fp exists and overlaps_decision_day(fp, decision_time_utc):
            if fp.precision in {HOUR, DAY, UNKNOWN}:
                raise IntradayPrecisionError

function release_eligible_as_of(release, decision_time_utc):
    validate_release_pit_constraints(release)
    validate_intraday_same_day_precision(release, decision_time_utc)  # when enabled
    return effective_available_at(release.available_at) <= decision_time_utc
```

## 8) Backward-compatibility constraints for configurability

If configurability is introduced, preserve safety and existing behavior:

1. Defaults remain strict (`intraday_same_day=True`).
2. Relaxed mode requires explicit non-empty operator intent metadata (`intraday_override_reason`).
3. Optional compatibility soft-fail may preserve strict behavior when legacy callers omit override reason (`soft_fail_intraday_override=True` => do not relax; keep strict).
4. Never make permissive behavior the default.
5. Any new precision/source policy toggle must be deterministic and documented with exact boundary semantics.

## 9) Inline code-doc rationale text (copy-ready)

Use/adapt the following inline comments in consumer code:

1.
"Conservative precision bounds: treat every timestamp as [lower, upper) and only assume guaranteed availability at upper. This prevents false precision from coarse source timestamps."

2.
"Half-open intervals make boundary behavior deterministic: exact upper-bound equality is eligible; any instant before upper is not."

3.
"Same-day intraday gating is overlap-based in UTC day space, not raw date equality, so midnight and hour-crossing edge cases are handled consistently."

4.
"UNKNOWN precision is handled as UTC day precision by default (safe fallback): uncertainty can only restrict eligibility, never expand it."

5.
"Forecast values require explicit provenance (observed time, source id, source version). Field names alone are not PIT evidence."
