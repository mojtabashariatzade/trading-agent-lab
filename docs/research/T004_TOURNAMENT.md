# T004 synthetic research tournament

This stage is an integration proof, not a performance result.

## Scope

- Connect the three T003 experts to a deterministic rule-based Decision Core.
- Route every executed decision through the single T002 ExecutionKernel.
- Replay one account chronologically so overlapping opportunities are not summed as if capital were duplicated.
- Save proposals, decisions, trades, strategy versions, execution configuration and run metadata as one JSON audit artifact.
- Use local fixtures only.

## Decision outcomes

The Decision Core treats these as explicit outcomes:

- DATA_REQUIRED: required M15, entry quote or M1 execution data is absent.
- RISK_VETO: data exists but risk permission is false.
- POSITION_OPEN: an earlier account trade is still open at the new decision time.
- ALL_PASS: experts produced no actionable proposal.
- DIRECTION_CONFLICT: actionable experts disagree on BUY versus SELL.
- MULTIPLE_NATIVE_PROPOSALS: multiple same-direction native-exit proposals cannot be combined without an arbitrary hidden ranking.
- SINGLE_EXPERT: one eligible proposal is executable.
- SHARED_EXIT_CONSENSUS: multiple same-direction experts agree while using the identical shared exit configuration.

There is deliberately no best-strategy or winner selection in this fixture stage.

## Synthetic-only guard

Every run is labelled SYNTHETIC_TEST_ONLY. The run object reports leaderboard_eligible = false and rejects attempts to emit real-performance rows. Fixture P&L is test evidence for execution/account semantics only.

## Audit artifact

write_run_artifact saves:

- run id and dataset id,
- SYNTHETIC_TEST_ONLY classification,
- strategy ids and versions,
- tournament/execution configuration,
- every strategy proposal,
- every Decision Core result,
- every executed trade,
- final single-account cash,
- an explicit warning that the artifact is not real historical performance.

## Safety

No downloader, broker API, credential, order submission, or Live trading function is introduced by T004.
