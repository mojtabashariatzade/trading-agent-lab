# Forecast downstream usage + PIT risk audit (t_e03f147a)

## Scope and method
- Scope: downstream consumers/transformers of forecast-related fields after ingest in `trading_lab/`.
- Search basis: `EconomicRelease`, `pre_release_forecast*`, `release_as_of`, `releases_as_of`, `original_macro_value`, and related provenance/integrity bindings.
- Result: current repo has a small set of direct consumers; no separate feature-builder/aggregator/model-prep pipeline exists yet.

## Inventory of downstream paths

| Priority | Path | Current behavior | PIT/semantic guard state | Invalid-record leakage mode | Explicit metadata signals already available |
|---|---|---|---|---|---|
| P0 | `trading_lab/fundamentals/schema.py:470` `releases_as_of(...)` (and wrapper `release_as_of` at `:500`) | Filters releases by `available_at <= decision_time`, optional same-day precision checks, then picks latest by `(available_at, revision_seq)` per key. | Strong: calls `validate_release_pit_constraints(release)` (`:481`) and `validate_intraday_same_day_precision(...)` (`:485`) before selection. | Low in normal flow; if callers bypass `intraday_same_day=True` they can intentionally relax same-day precision blocking and include ambiguous intraday timing. | `available_at`, `observed_at`, `published_at`, `scheduled_at` (`TimePoint.precision`), `pre_release_forecast_observed_at`, `pre_release_forecast_source_id`, `pre_release_forecast_source_version`, `revision_seq`. |
| P0 | `trading_lab/data/sampling.py:162` `original_macro_value(release)` | Returns immutable first-release value (`first_actual`) and never substitutes revision. | Strong: re-validates via `validate_release_pit_constraints(release)` (`:164`) before returning value. | Low in normal flow; only mutated/legacy-invalid objects could leak, but they are blocked by re-validation. | `first_actual`, `pre_release_forecast*` integrity conditions enforced by validator; source capability via source registry. |
| P1 | `trading_lab/fundamentals/schema.py:141` `EconomicRelease.surprise()` | Computes `first_actual - pre_release_forecast`, returns `None` if either missing. | Partial: relies on object construction-time validation, but does **not** call `validate_release_pit_constraints` at read time. | If a legacy/mutated `EconomicRelease` instance exists (e.g., via `object.__setattr__` in legacy migration paths), stale/invalid forecast provenance could still be used in surprise calculation. | `first_actual`, `pre_release_forecast`, plus available validator signals: `pre_release_forecast_observed_at`, `pre_release_forecast_source_id`, `pre_release_forecast_source_version`. |
| P1 | `trading_lab/fundamentals/schema.py:334` `parse_release_payload(payload)` (ingest boundary feeding downstream) | Converts mapping to typed `EconomicRelease`; collects deterministic PIT issues. | Strong at parse-time: enforces required fields and full PIT validation through model construction + structured errors. | Unknown/extra legacy hint fields are ignored; malformed forecast metadata is rejected, so leakage risk is low unless callers skip this parser entirely and instantiate/mutate manually. | Full schema fields + deterministic issue codes (`PIT_FORECAST_*`, `PARSER_*`). |

## Additional integrity/provenance controls relevant to forecast trust

1. Source capability gate
- `trading_lab/fundamentals/schema.py:214` `_validate_forecast_source(...)` ensures `pre_release_forecast_source_id` is registered and `SourceKind.LICENSED_FORECAST`.
- Registry entry is explicit placeholder class in `trading_lab/fundamentals/registry.py:101` (`licensed_forecast_provider`), preventing accidental trust in non-forecast sources.

2. Immutable data/provenance binding (upstream of release modeling)
- `trading_lab/data/imports.py:493` `verify_manifest_bindings(...)` enforces:
  - required snapshot artifacts (`:502-505`)
  - required provenance pair `source_provenance` + `legal_source` (`:506-507`)
  - payload/record hash checks (`:514-535`)
  - metadata-to-record and timestamp/gap consistency (`:536-568`)
- This does not validate forecast semantics directly, but provides hard signals to reject unbound/tampered upstream data that would otherwise feed release construction.

## Observed gap map

1. No multi-stage downstream forecast feature pipeline yet
- No dedicated forecast feature builders, aggregators, exporters, or model-prep modules consume `pre_release_forecast*` today.
- Practical implication: current risk is concentrated in helper methods and future expansion points rather than many active consumers.

2. Read-time guard inconsistency
- `releases_as_of` and `original_macro_value` re-validate at use-time, but `EconomicRelease.surprise()` does not.
- This is the main inconsistency where inferred semantics can be trusted without an explicit read-time PIT check.

3. Policy override surface
- `releases_as_of(..., intraday_same_day=False)` can disable same-day precision protections by design.
- Not a bug by itself, but a governance risk unless call-sites must explicitly justify or log this override.

## Prioritized remediation list

1. P0: Add explicit policy wrapper for release selection
- Introduce a single approved entrypoint (e.g., `select_release_for_intraday_decision`) that hard-locks `intraday_same_day=True` unless a documented override token/flag is provided.
- Require call-sites to use wrapper rather than raw `releases_as_of`.

2. P1: Make `surprise()` read-time safe
- Either (a) call `validate_release_pit_constraints(self)` inside `EconomicRelease.surprise()`, or (b) add a dedicated `validated_surprise(release)` helper and deprecate direct arithmetic in `surprise()`.
- This aligns behavior with `original_macro_value` and closes mutated-legacy leakage risk.

3. P1: Add negative tests for policy bypass and mutated instances
- Add tests proving that invalid/mutated forecast provenance fails at all downstream read paths (including surprise computation path after remediation).
- Add tests for `intraday_same_day=False` requiring explicit operator intent marker (after wrapper introduction).

4. P2: Forecast-usage registry for future modules
- Add a lightweight inventory map (module/function annotations or a central registry) for any new consumer of `pre_release_forecast*` fields so PIT checks are auditable as the codebase expands.

## Bottom line
- Current active downstream forecast consumers are limited and mostly guarded.
- Highest practical risk is not broad leakage today, but inconsistent read-time validation (`surprise`) and future call-site drift around `intraday_same_day` policy overrides.
