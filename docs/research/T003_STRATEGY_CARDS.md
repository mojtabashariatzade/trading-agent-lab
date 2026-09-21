# T003 strategy cards

All three experts are deterministic research components. They produce proposals only; none can submit orders or contact a broker. All inputs must be closed bars. These cards define behavior, not profitability claims.

## EMA_TREND v1.0.0

- Family: trend / moving-average crossover.
- Input: strictly ordered closed bars with no gap inside the required lookback.
- Entry proposal: BUY when the fast EMA crosses above the slow EMA on the newest closed bar; SELL on the inverse crossover; otherwise PASS.
- Default parameters: fast 5, slow 12.
- Bounded search rule: fast >= 2, slow > fast, and both must remain fixed/versioned inside an experiment.
- Native exit: stop distance 0.30, target distance 0.60 price units.
- Invalidation: insufficient history, data gap, open bar, malformed timestamps/OHLC.
- Expiry: two source bars by default.

## BOLLINGER_REENTRY v1.0.0

- Family: mean reversion / Bollinger re-entry.
- Input: strictly ordered closed bars with no gap inside the required lookback.
- Entry proposal: BUY when the previous close was below its causal lower envelope and the newest close re-enters; SELL for the symmetric upper-envelope re-entry; otherwise PASS.
- Default parameters: window 20, deviations 2.0.
- Bounded search rule: window must be positive and deviations positive; experiment ranges must be declared before evaluation.
- Native exit: stop distance 0.25, target distance 0.40 price units.
- Invalidation: insufficient history, data gap, open bar, malformed timestamps/OHLC.
- Expiry: two source bars by default.

## SESSION_RANGE_BREAKOUT v1.0.0

- Family: session breakout.
- Input: closed bars plus an explicit IANA timezone. Default session timezone is Europe/London.
- Session definition: local 08:00 inclusive to 09:00 exclusive. Time conversion uses zoneinfo, so DST is not represented by a fixed UTC offset.
- Entry proposal: after the range has closed, BUY when the newest close is above the session range high; SELL below the range low; otherwise PASS.
- Native exit: stop distance 0.35, target distance 0.70 price units.
- Invalidation: missing session range, relevant data gap, open bar, malformed timestamps/OHLC.
- Expiry: four source bars by default.

## Exit leagues

Two leagues are intentionally separate:

- NATIVE: each expert uses its own versioned exit configuration.
- SHARED: all experts receive the same externally supplied ExitConfig.

A SHARED proposal without an explicit shared exit is rejected. This keeps comparisons between shared-exit and native-exit experiments auditable instead of silently mixing the two.

## Research status

UNTESTED on real historical GBPJPY data. The acceptance tests cover determinism, expiry, no-signal behavior, closed-bar enforcement, exit-league separation, and London DST handling only.
