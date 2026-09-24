# T005 PIT downstream enforcement: compatibility and migration notes

Purpose: implementation guidance for rolling out stricter downstream point-in-time (PIT) checks in `trading_lab/fundamentals/schema.py` without silently corrupting historical research behavior.

Scope: this note covers compatibility impact, migration-safe handling, phased rollout/rollback, and monitoring for newly rejected rows.

## 1) What changed in downstream behavior

Recent G07 updates enforce PIT constraints not only at ingest, but also at read-time use:

- `EconomicRelease.surprise()` now re-validates PIT constraints before using forecast fields.
  - strict default: raises `PITValidationError` on invalid/mutated legacy records.
  - compatibility option: `soft_fail_on_pit_error=True` returns `None` instead of raising.
- `releases_as_of(...)` validates each release at selection time and applies conservative precision checks for same-day intraday.
- `releases_as_of(..., intraday_same_day=False)` now requires non-empty `intraday_override_reason`.
  - compatibility option: `soft_fail_intraday_override=True` keeps strict intraday mode if reason is missing.

Implication: rows that previously flowed through downstream consumers due to legacy mutation, missing metadata, or lax call patterns can now be rejected or downgraded to `None`.

## 2) Compatibility risks for historical stored data

Historical/backfilled datasets may contain one or more of these now-blocking states:

- Forecast value present but required forecast metadata missing (`*_observed_at`, `*_source_id`, `*_source_version`).
- Forecast metadata present while forecast value is null.
- Forecast source id not registered or not `LICENSED_FORECAST` capable.
- Forecast observation chronology after `published_at` or `available_at`.
- Coarse same-day intraday precision (`DAY`/`UNKNOWN`, and for forecast observed time also `HOUR`).
- Legacy callers setting `intraday_same_day=False` without explicit operator reason.

Expected symptom set after enabling strict read-time enforcement:

- `PITValidationError` at downstream selection/surprise computation.
- `IntradayPrecisionError` for same-day ambiguous precision.
- Increased `None` outputs where soft-fail paths are intentionally enabled.

## 3) Migration-safe handling strategy

Recommended phased approach:

### Phase A — Inventory and quantify (no behavior change)

1. Run an offline audit over stored release rows by constructing `EconomicRelease` and collecting PIT issues.
2. Aggregate by `PITValidationIssue.code` and source ids.
3. Record baseline counts and impacted `(jurisdiction, indicator, event_period)` keys.

Goal: measure breakage risk before strict downstream cutover.

### Phase B — Quarantine and reporting

Introduce a deterministic quarantine flow for invalid rows:

- Do not silently pass PIT-invalid rows to ranking/selection logic.
- Route invalid rows to a quarantine/report stream with:
  - release key fields
  - source/source_version
  - issue codes/messages
  - first-seen timestamp
- Keep valid rows available for as-of selection.

If storage schema cannot be changed immediately, a temporary side-report (JSON/CSV artifact in research pipeline outputs) is acceptable.

### Phase C — Repair or nullify

For quarantined historical rows, use one of two explicit remediations:

1) Repair path (preferred when provenance can be proven)
- Backfill missing forecast metadata from trusted historical collector evidence.
- Ensure source id maps to registered `LICENSED_FORECAST` kind.
- Preserve chronology constraints.

2) Nullification path (safe fallback)
- Set `pre_release_forecast` and all forecast metadata fields to null together.
- This preserves row usability for non-forecast logic while preventing invalid surprise usage.

Do not fabricate timestamps or source versions.

### Phase D — Grandfathering window (time-boxed)

Optionally run a short transition window where:

- strict validation remains enabled,
- `soft_fail_on_pit_error=True` is used only at selected downstream call sites,
- every soft-fail event is logged/metriced,
- SLA is to drive soft-fail count to zero before full strict mode.

This avoids abrupt pipeline failure while still exposing data debt.

### Phase E — Full strict mode

After repair/nullification backlog is cleared and soft-fail counts are stable at (or near) zero:

- disable soft-fail compatibility paths,
- require explicit intraday override reason for policy relaxations,
- treat new invalid rows as ingestion/data-quality defects.

## 4) Rollout runbook

1. Baseline audit report generated and stored with counts by issue code.
2. Quarantine/reporting enabled in downstream pipeline.
3. Backfill/nullification scripts executed on historical violating rows.
4. Targeted tests run:
   - `python -m unittest tests.added.test_t005_fundamentals tests.added.test_t006_sampling_readiness -v`
5. Full suite run:
   - `python -m unittest discover -s tests -v`
6. Deploy with compatibility flags only if audit backlog remains.
7. Remove compatibility flags after two clean cycles (project-defined cadence).

## 5) Rollback guidance

If strict rollout causes unacceptable downstream interruption:

Immediate containment
- Re-enable compatibility toggles at call sites (`soft_fail_on_pit_error=True`, and where needed `soft_fail_intraday_override=True`).
- Keep quarantine/reporting on; do not disable visibility.

Stabilization
- Re-run PIT issue inventory to identify remaining invalid cohorts.
- Prioritize repair/nullification on highest-volume issue codes.

Exit rollback mode
- Return to strict mode once backlog and soft-fail metrics are back within acceptance thresholds.

Important: rollback should relax failure mode, not remove PIT validation codepaths.

## 6) Monitoring and alerting for newly rejected records

Track at minimum:

- Count of `PITValidationError` by `issue.code`.
- Count of `IntradayPrecisionError` by field/precision pair.
- Count of `surprise(..., soft_fail_on_pit_error=True)` fallbacks returning `None` due to PIT issues.
- Count of `intraday_same_day=False` calls and fraction with explicit override reason.
- Quarantine backlog size and age (oldest unresolved invalid row).

Recommended alert thresholds (tune per environment):

- Any non-zero daily count for new issue codes not seen in baseline.
- Quarantine backlog age exceeding agreed remediation SLA.
- Soft-fail fallback rate above agreed transition threshold.

## 7) Non-goals and guardrails

- No changes to Trading Decision Core ranking policy are introduced by this migration.
- No synthetic forecast/provenance data may be invented to satisfy validators.
- PIT policy exceptions must be explicit, reviewable, and time-boxed.

## 8) PR/reference checklist

When referencing this migration in a PR, include:

- Link to this document.
- Baseline issue-code histogram before cutover.
- Chosen compatibility mode (strict vs grandfathering) and expected end date if grandfathering is used.
- Evidence of targeted + full test runs.
