# Product contract -- approved research direction, not evidence of profitability

## Objective
Build a GBPJPY/M15 multi-strategy research and decision system. Candidate complete
strategies compete, complementary specialists are selected, and a learnable
Decision Core chooses one eligible proposal or PASS. The system may progress
through historical research, unseen evaluation, shadow, paper, and eventually an
independently authorized small live pilot. This starter contains NO live adapter.

The user's original source emphasizes equal execution conditions, causal data,
chronological evaluation, realistic costs and not mistaking a beautiful backtest
for reliable performance. Later conversation explicitly expands the scope to
strategy specialists (not merely ML algorithm names), fundamentals from credible
sources, and a supervised autonomous SOFTWARE-DEVELOPMENT team.

## Keep two separate control systems
1. Development Core: issue/task state, worker runs, QA, evidence, owner approvals.
2. Trading Decision Core: proposals, market state, risk veto and position handling.
Software-development agents never receive broker credentials or trading authority.

## Fifteen proposed expert families (all UNTESTED)
S01 EMA trend; S02 Donchian breakout; S03 volatility compression breakout;
S04 session range breakout; S05 trend pullback; S06 RSI mean reversion;
S07 Bollinger re-entry; S08 failed breakout; S09 multi-timeframe alignment;
S10 currency-basket strength; S11 rate/yield context with a short-horizon entry;
S12 UK macro surprise; S13 Japan macro surprise; S14 central-bank statement change;
S15 reversal after a news shock. Overlapping families are not presumed independent.
Exact mathematical rules, source/license, horizon and bounded search precede tests.
There is no mandate to retain all fifteen or to find a profitable winner.

## Separate competitions
- Signal league: common entry/exits, ATR14 stop, 3R target, 240 real minutes.
- Full-system league: strategy-native registered exits; equal risk/cost conventions.
- Core league: preselected single specialist, deterministic selector, fixed blend,
  supervised selector and (later) small neural selector, with common account rules.
Do not silently force a native mean-reversion system into the signal-league exit
and then report it as the performance of the original system.

## Price and execution
UTC timezone-aware data. Event time and availability time are separate. Only
closed M15/H1/H4 bars. Half-open intervals; no boundary quote used twice. Keep bid
and ask; buy at executable ask, close at bid, and vice versa. Fill after decision
readiness and configured latency, not retrospectively at an unavailable candle
open. ATR uses past closed bars only. Include spread exactly once, commissions,
slippage, gap losses and rollover where relevant. TIMEOUT realizes P&L, not zero.
M1 ambiguous order of touch: flag + conservative SL-first. Tick replay preferred.
Censored/invalid data is not a fabricated win/loss. Do not delete failed live
paths retrospectively simply because future data is incomplete.
One replay kernel for hypothetical outcomes AND portfolio execution. Respect
single-position, pending-order, cash/margin and overlapping-signal constraints.
Synthetic data is test-only and never enters a performance leaderboard.

## Fundamental and news layer -- start schema/archive work in phase 1
Use official actual releases (ONS/BoE/BoJ/Statistics Bureau/ESRI/MOF/Fed/BLS/BEA),
licensed consensus calendars where appropriate, and Forex Factory as a secondary
calendar cross-check. Evaluate Trading Economics point-in-time history and
ALFRED vintages, without claiming every series has complete intraday history.
Require provider terms/license, first-release values, forecast as known before
release, previous as known, revisions, scheduled time, release time, observed
and usable time, source and precision. Only join on available_at. Daily vintages
cannot establish minute-level availability. Missing forecast is unknown, not 0.
No fixed rule that a higher CPI must mechanically imply BUY GBPJPY. News can
veto trading separately from predicting direction. NLP extracts structured facts;
it cannot send orders. Archive revised and duplicate headlines separately.
No purchased feed, large scrape or credential use without explicit authorization.

## Validation
Target price history begins 2016 if actual coverage permits. 2016-2022 development
training, 2023-2024 selection/calibration with nested temporal splits, 2025 reserved
evaluation and 2026 partial-year holdout only if genuinely untouched. Preserve
actual data_end_utc. Once a period influences design, it is not unseen again.
Purging uses the actual last information timestamp of each label and each
specialist's exit horizon. No random splits. Fit transforms, selection, calibration,
regimes and meta-model only on permitted past data. Select specialists INSIDE the
walk-forward process, not using the full future first. Record all experiment
attempts, selection budget, multiple-testing risk and block-bootstrap uncertainty.
No certainty from a fixed trade count; report independent events for news models.
A learned Core trains on temporal out-of-sample specialist predictions. Compare
components with ablations under equal costs. Model confidence is not inherently
calibrated. Failure to find an edge is an acceptable outcome.

## Research extensions
GRU/TCN and small neural gating are candidates, not mandatory production choices.
Reinforcement learning and fly-connectome-inspired networks are separate later
experiments. Match compute, data, features and execution; compare biological
connectivity with random/topology controls. Never describe inspiration as proof.
No money-making claim is established by this starter or its synthetic tests.

## Gates
Phase 1 contains six bounded implementation tasks. Later tasks are visible but
not executable without a reviewed controller/backlog release. Funding/paid data,
control-plane changes, secrets, risk increases and live deployment are owner gates.
Initial merge policy: one owner Telegram approval per exact green reviewed PR.
No unattended self-modification of the development control plane. Never deploy
this controller automatically on every research-repository commit.
