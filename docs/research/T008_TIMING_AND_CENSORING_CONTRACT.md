# T008 Timing and censoring contract (Issue #53)

## Canonical timestamps

- `event_time_utc`: when the market event happened (e.g., quote timestamp).
- `available_at_utc`: when that event is usable by the strategy.
- `fill_ready_at_utc`: `max(event_time_utc, available_at_utc) + configured_entry_latency`.

For M1 replay, all three are minute-aligned UTC timestamps.

## Entry eligibility

Tournament entry eligibility is causal and requires:

1. closed M15 inputs,
2. a present entry quote,
3. `entry_quote.event_time_utc <= decision_at_utc`,
4. `entry_quote.available_at_utc <= decision_at_utc`.

Missing or not-yet-available quote data yields `DATA_REQUIRED` rather than a fabricated trade.

## Execution boundary semantics

- Timeout must be strictly after `fill_ready_at_utc`.
- M1 bars before `fill_ready_at_utc` are ignored for TP/SL/timeout evaluation.
- At timeout exactly on a bar start, timeout exits at the bar open quote before intrabar TP/SL checks.
- At timeout exactly on a bar end, timeout exits at the bar close quote.

## Censored vs realized outcomes

- **Realized P&L** (`TP`, `SL`, `TIMEOUT`): `exit_at`, `exit_price`, `gross_pnl`, and `net_pnl` are concrete values.
- **Censored outcome** (`CENSORED`): future execution path is unavailable; no fabricated close is created.
  - `exit_at` and `net_pnl` remain `None`.
  - The account position stays open and blocks overlapping entries until resolved by later data.

This preserves causality and avoids changing prior entry decisions due to missing future prices.
