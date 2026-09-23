# Issue #40 (P1) execution plan: integrity gates only

Purpose: close the remaining #40 integrity gates (G06/G07/G08/G16) without changing Trading Decision Core ranking/selection behavior.

## 1) Scope boundary: Development Core vs Trading Decision Core

Development Core work (in scope):
- Data/import manifest integrity and provenance checks.
- Forecast provenance + availability-time validation.
- Accounting/risk invariant specification and deterministic gate tests.
- Temporal split/purging boundary validation utilities and tests.
- Evidence generation for PR review (tests, fixtures, failure-mode coverage).

Trading Decision Core work (out of scope):
- No changes to proposal generation/ranking policy.
- No changes to decision logic thresholds for LONG/SHORT/PASS.
- No strategy scoring redesign, no leaderboard semantics rewrite.

Guardrail: if a change affects ranking/selection semantics, split it into a separate issue/PR and keep #40 PR integrity-only.

## 2) Prohibited actions (explicit)

- Do not use Jira/CPI/SUP/Vendoroo.
- Do not enable broker/live trading.
- Do not enable paid data/services or new paid providers.
- Do not add credentials/secrets or environment-token dependencies.
- Do not push directly to `main`.

## 3) Planned workstreams and expected modules

### G06: metadata bound to parsed bytes
Primary targets:
- `trading_lab/data/imports.py`
- `trading_lab/data/sampling.py`
- `tests/added/test_t006_sampling_readiness.py`
- (if needed) new helper module under `trading_lab/data/` for binding verification logic.

Acceptance intent:
- Manifest/checksum/snapshot linkage is fail-closed.
- Metadata/timestamp rows cannot drift from payload-derived records.
- Mutated payload or orphan metadata rows are rejected.

### G07: forecast provenance and conservative availability
Primary targets:
- `trading_lab/fundamentals/schema.py`
- `tests/added/test_t005_fundamentals.py`
- `tests/added/test_t006_sampling_readiness.py` (cross-check as-of behavior)
- `docs/research/T005_PIT_COMPATIBILITY_AND_MIGRATION.md` (rollout/rollback + legacy-data handling notes)

Acceptance intent:
- Forecast values require observed_at + source id/version provenance.
- Same-day intraday precision remains conservative (no hour/day ambiguity leakage).
- Releases unavailable at decision time remain excluded.

### G08: account-currency P&L and risk invariants
Primary targets:
- `trading_lab/contracts.py` (only deterministic accounting invariants, not ranking policy)
- `tests/added/test_issue40_accounting_gates.py`
- optional new focused test file in `tests/added/` for currency/fee vector edge cases.

Acceptance intent:
- Hand-checkable vectors for equity/cash/margin/rollover/overlap are enforced.
- Any accounting mismatch blocks decision eligibility before ranking.

### G16: purging and temporal split boundaries
Primary targets:
- New or existing split/validation utility under `trading_lab/research/` or `trading_lab/data/`.
- New tests under `tests/added/` for purge-window and boundary edge cases.

Acceptance intent:
- Training labels cannot overlap forbidden future/evaluation information.
- Boundary tests cover exact-edge timestamps and horizon-derived purge windows.

## 4) Test strategy

1. Keep all added/changed tests under `tests/added/`.
2. Add explicit failure-mode tests per gate (tamper, missing provenance, boundary overlap).
3. Run full suite command after each coherent increment:
   - `python -m unittest discover -s tests -v`
4. For fast iteration, run targeted files first, then full suite before PR update.
5. Include before/after notes in PR description: which failure mode was reproduced and what now blocks/passes.

## 5) Branch + PR workflow checklist (never push to main)

1. Sync default branch locally.
2. Create feature branch for #40 gate work (example: `feat/issue-40-integrity-gates`).
3. Implement one gate-focused slice at a time (G06 -> G07 -> G08 -> G16) with tests.
4. Run targeted tests, then `python -m unittest discover -s tests -v`.
5. Commit with scoped messages (one logical change per commit).
6. Push branch and open non-draft PR.
7. PR description must include:
   - Scope statement: Development Core integrity only; no Trading Decision Core ranking changes.
   - Gate checklist (G06/G07/G08/G16) with evidence links.
   - Risks/known limitations and any deferred follow-ups.
8. Request QA review; do not merge without reviewed green evidence.
9. If any gate remains incomplete, keep PR explicit about blocked items (no implied closure).

## 6) Done criteria for this issue plan

- Execution plan and checklist are explicit enough to copy into PR description.
- Scope/prohibitions are unambiguous.
- File/test touchpoints are identified per gate.
- No live-trading, paid-service, or control-plane expansion introduced.
