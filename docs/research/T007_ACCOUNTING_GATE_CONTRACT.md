# T007 deterministic accounting gates before ranking

Status: SPEC READY FOR IMPLEMENTATION AND TESTING

## Purpose

Define deterministic pre-ranking accounting gates that run before any strategy/model ranking. If any gate fails, decision output is PASS with a blocking reason and no candidate strategy_id.

## Execution point and control flow

1) Input snapshot validation (shared pre-check).
2) MTM gate.
3) Cash gate.
4) Margin gate.
5) Overlap gate.
6) Rollover gate.
7) Only if all pass: proceed to eligibility filtering and ranking.

Short-circuit: stop at first failure in the fixed order above.

Blocking policy: all failures in this document are HARD_BLOCK (ranking is skipped).

## Shared input snapshot contract

Required top-level fields for the accounting snapshot used by all gates:

- decision_time_utc: timezone-aware UTC datetime.
- account_snapshot_time_utc: timezone-aware UTC datetime of account state.
- max_snapshot_age_seconds: non-negative integer.
- instrument: non-empty symbol string (example: GBPJPY).
- account_currency: non-empty ISO currency code.

Shared pre-check rules:

- If any required field is missing/null -> ACCOUNTING_BLOCK_INPUT_MISSING.
- If any numeric field used by a gate is NaN/inf -> ACCOUNTING_BLOCK_INPUT_NONFINITE.
- If account_snapshot_time_utc > decision_time_utc -> ACCOUNTING_BLOCK_SNAPSHOT_FUTURE.
- If (decision_time_utc - account_snapshot_time_utc).seconds > max_snapshot_age_seconds -> ACCOUNTING_BLOCK_SNAPSHOT_STALE.

All shared pre-check failures are HARD_BLOCK and occur before gate 1.

## Gate 1: Mark-to-market (MTM)

Required inputs:

- equity
- cash_available
- unrealized_pnl
- mtm_tolerance_abs (>= 0)

Validation rule:

- expected_equity = cash_available + unrealized_pnl
- delta = abs(equity - expected_equity)

Pass condition:

- delta <= mtm_tolerance_abs

Fail condition:

- delta > mtm_tolerance_abs

Failure contract:

- error_code: ACCOUNTING_BLOCK_MTM
- error_message: "MTM mismatch: equity must equal cash_available + unrealized_pnl within tolerance"
- block_type: HARD_BLOCK

## Gate 2: Cash

Required inputs:

- cash_available
- min_cash_required

Validation rule:

- min_cash_required must be >= 0

Pass condition:

- cash_available >= min_cash_required

Fail conditions:

- min_cash_required < 0 (invalid config)
- cash_available < min_cash_required

Failure contract:

- error_code: ACCOUNTING_BLOCK_CASH
- error_message: "Insufficient cash: cash_available is below min_cash_required"
- block_type: HARD_BLOCK

## Gate 3: Margin

Required inputs:

- free_margin
- required_margin

Validation rule:

- required_margin must be >= 0

Pass condition:

- free_margin >= required_margin

Fail conditions:

- required_margin < 0 (invalid config)
- free_margin < required_margin

Failure contract:

- error_code: ACCOUNTING_BLOCK_MARGIN
- error_message: "Insufficient free margin: free_margin is below required_margin"
- block_type: HARD_BLOCK

## Gate 4: Overlap

Required inputs:

- overlap_detected (bool)
- net_exposure_after_candidate (signed quantity in account units)
- max_abs_exposure_limit (>= 0)
- open_positions_same_instrument (integer >= 0)
- max_positions_same_instrument (integer >= 0)

Validation rules:

- open_positions_same_instrument and max_positions_same_instrument must be non-negative integers.
- max_abs_exposure_limit must be >= 0.

Pass condition:

- overlap_detected == false
- abs(net_exposure_after_candidate) <= max_abs_exposure_limit
- open_positions_same_instrument <= max_positions_same_instrument

Fail conditions:

- overlap_detected == true
- abs(net_exposure_after_candidate) > max_abs_exposure_limit
- open_positions_same_instrument > max_positions_same_instrument

Failure contract:

- error_code: ACCOUNTING_BLOCK_OVERLAP
- error_message: "Exposure overlap/limit violation for candidate instrument"
- block_type: HARD_BLOCK

## Gate 5: Rollover

Required inputs:

- rollover_due
- rollover_charged
- rollover_tolerance_abs (>= 0)
- rollover_due_date_utc (date)
- rollover_charge_date_utc (date)

Validation rules:

- date fields must exist and be parseable UTC dates.

Pass condition:

- abs(rollover_due - rollover_charged) <= rollover_tolerance_abs
- rollover_due_date_utc == rollover_charge_date_utc

Fail conditions:

- absolute amount mismatch above tolerance
- rollover_due_date_utc != rollover_charge_date_utc

Failure contract:

- error_code: ACCOUNTING_BLOCK_ROLLOVER
- error_message: "Rollover mismatch: amount/date inconsistent with due rollover"
- block_type: HARD_BLOCK

## Edge-case requirements

The following must yield deterministic PASS/FAIL without silent fallback:

1) Missing required field -> shared pre-check fail with ACCOUNTING_BLOCK_INPUT_MISSING.
2) NaN/inf numeric values -> shared pre-check fail with ACCOUNTING_BLOCK_INPUT_NONFINITE.
3) Stale snapshot timestamp -> shared pre-check fail with ACCOUNTING_BLOCK_SNAPSHOT_STALE.
4) Negative balances:
   - negative cash_available is allowed only if still >= min_cash_required; otherwise CASH fail.
   - negative min_cash_required or required_margin is invalid and fails their gate.
5) Impossible exposures:
   - abs(net_exposure_after_candidate) above limit or position count above cap -> OVERLAP fail.
6) Rollover date mismatch -> ROLLOVER fail even if amount matches.

## Deterministic return behavior

When blocked, return:

- side: PASS
- strategy_id: null
- reason: first failing error_code (short-circuit order)

No ranking, tie-breaking, or EV filtering runs after a block.

## Required telemetry/audit log fields per decision

Emit one structured record for each decision-time evaluation:

- decision_id (stable unique id)
- decision_time_utc
- account_snapshot_time_utc
- snapshot_age_seconds
- instrument
- account_currency
- gate_order (fixed list)
- gate_results (array in order):
  - gate_name
  - status (PASS|FAIL|SKIP)
  - error_code (null on PASS)
  - error_message (null on PASS)
  - measured_values (only fields used by that gate)
  - thresholds_used
- blocked (bool)
- block_error_code (null if not blocked)
- ranking_executed (bool)

Audit requirements:

- Logs must preserve evaluation order exactly.
- SKIP is only allowed for gates after the first failure (due to short-circuit).
- Numeric values must be logged at full internal precision (no rounded comparison in logic).

## Implementation checklist (code + tests)

1) Implement fixed-order gate evaluator with first-failure short-circuit.
2) Add shared pre-check for missing/non-finite/stale/future snapshot errors.
3) Implement MTM/CASH/MARGIN/OVERLAP/ROLLOVER rules exactly as above.
4) Ensure blocked result is PASS + null strategy_id + error_code reason.
5) Emit structured gate telemetry fields for every decision.
6) Unit tests: one PASS case per gate and one FAIL case per fail condition.
7) Unit tests: verify short-circuit order (later gates marked SKIP after first fail).
8) Unit tests: verify ranking is never called when any gate fails.
9) Unit tests: verify rollover date mismatch fail path.
10) Unit tests: verify NaN/missing/stale timestamp edge cases.
