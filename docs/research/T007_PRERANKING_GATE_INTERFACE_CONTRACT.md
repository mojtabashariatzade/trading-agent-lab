# T007 pre-ranking gate interface and reason-code contract

Status: SPEC READY FOR IMPLEMENTATION

## Purpose

Define a single deterministic gate layer contract that executes before any candidate ranking logic in `trading_lab/contracts.py::decide`. This keeps ranking/selection semantics unchanged while enforcing fail-closed eligibility checks.

This document is tailored to the current codebase and aligns with:
- `trading_lab/contracts.py` (`AccountingState`, `AccountingGateResult`, `AccountingGateEvaluation`, `decide`)
- `docs/research/T007_ACCOUNTING_GATE_CONTRACT.md` (gate rules and error-code semantics)

## 1) Gate evaluator interfaces: signatures and IO types

Code-level signatures (current + target-stable):

```python
# trading_lab/contracts.py
@dataclass(frozen=True)
class AccountingGateResult:
    gate_name: str
    status: str  # PASS | FAIL | SKIP
    error_code: str | None
    error_message: str | None
    measured_values: dict[str, object]
    thresholds_used: dict[str, object]

@dataclass(frozen=True)
class AccountingGateEvaluation:
    gate_order: tuple[str, ...]
    gate_results: tuple[AccountingGateResult, ...]
    blocked: bool
    block_error_code: str | None
    block_error_message: str | None

class AccountingState:
    def gate_evaluators(self) -> tuple[Callable[[], AccountingGateResult], ...]: ...
    def evaluate_gates(self) -> AccountingGateEvaluation: ...
```

Required evaluator behavior:
- Each evaluator returns exactly one `AccountingGateResult`.
- `gate_name` is stable and unique inside one evaluation run.
- `status` is one of `PASS`, `FAIL`, `SKIP`.
- `error_code`/`error_message` are both null on PASS/SKIP and both populated on FAIL.

## 2) Canonical pass/fail result schema and reason-code contract

Canonical per-gate result schema is `AccountingGateResult`.

Canonical aggregate schema is `AccountingGateEvaluation` with:
- `blocked == True` iff at least one gate has `status == FAIL`.
- `block_error_code` = first failing gate `error_code` in evaluation order.
- `block_error_message` = first failing gate `error_message` in evaluation order.

Canonical decision block mapping in `decide(...)`:
- If `evaluate_gates().blocked` is true:
  - return `Decision(side=Side.PASS, reason=block_error_code, strategy_id=None)`
- No ranking/EV/tie-break path may run after a block.

Stable reason-code namespace:
- Shared precheck: `ACCOUNTING_BLOCK_INPUT_MISSING`, `ACCOUNTING_BLOCK_INPUT_NONFINITE`, `ACCOUNTING_BLOCK_SNAPSHOT_FUTURE`, `ACCOUNTING_BLOCK_SNAPSHOT_STALE`
- Gate failures: `ACCOUNTING_BLOCK_MTM`, `ACCOUNTING_BLOCK_CASH`, `ACCOUNTING_BLOCK_MARGIN`, `ACCOUNTING_BLOCK_OVERLAP`, `ACCOUNTING_BLOCK_ROLLOVER`

Contract stability rules:
- `error_code` values are API-stable identifiers (not free text).
- `error_message` is human-readable and may be improved for clarity but must preserve meaning.
- Downstream checks should key on `error_code`, not message text.

## 3) Deterministic evaluation requirements

Non-negotiable determinism:
- No hidden dependency on wall clock (`datetime.now`), randomness, process state, network, or mutable globals.
- Only explicit inputs on `AccountingState` fields participate in gate decisions.
- Time logic must use `decision_time_utc` and `account_snapshot_time_utc` supplied by caller.
- Evaluation order is fixed (`INPUT_PRECHECK` then declared gate order).
- First failure short-circuits later gates to `SKIP` with empty measurement payloads.

Deterministic logging shape (already represented by result objects):
- Preserve gate order exactly.
- Preserve measured values and thresholds used for each evaluated gate.
- Store numeric values without changing comparison semantics.

## 4) Extension mechanism without changing call sites

Current extension point is `AccountingState.gate_evaluators()`.

Extension contract:
1. Add a new gate evaluator method returning `AccountingGateResult`.
2. Insert its callable into `gate_evaluators()` in the intended fixed order.
3. Add its stable gate name to `GATE_ORDER`.
4. Add deterministic tests for PASS, FAIL, and short-circuit interaction.

Call-site stability requirement:
- `decide(...)` must continue to call only `evaluate_gates()` and inspect `blocked`/`block_error_code`.
- No ranking call site may need to know specific gate implementations.

## 5) Earliest pre-ranking integration point per candidate

Primary integration point in current codebase:
- `trading_lab/contracts.py::decide(...)`
- Placement: after top-level vetoes (`DATA_UNAVAILABLE`, `RISK_BLOCK`, `POSITION_OPEN`) and before computing `eligible` assessments, sorting, or direction-gap checks.

Execution sequence in `decide(...)`:
1. Validate deterministic top-level preconditions.
2. Run `accounting_state.evaluate_gates()`.
3. If blocked: return PASS with blocking reason_code and `strategy_id=None`.
4. Only then execute proposal eligibility filter and ranking logic.

Rationale for this placement:
- It is the earliest shared stage that can prevent any ranking consumption when accounting integrity fails.
- It preserves existing decision semantics for all non-blocked paths.

## Acceptance checklist for this interface contract

- Evaluator signatures and output dataclasses are explicit and implementable.
- Reason-code contract is stable and machine-parseable.
- Deterministic requirements prohibit hidden state/time/randomness.
- New gates can be added only through `gate_evaluators`/`GATE_ORDER`, with unchanged callers.
- Integration point is clearly fixed before any candidate ranking work.