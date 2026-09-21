# Trading profit and account-performance plan

Version 1.2 | 22 September 2026 | Replaces the out-of-scope sales plan

## 1. The income objective

The system is intended to trade the owner's account automatically: observe markets, decide whether to open LONG or SHORT, size a permitted position, execute it, manage it, exit it and reconcile its net profit or loss. PASS, WAIT and DATA_INSUFFICIENT are legitimate decisions when entry conditions are absent. The intended income is net P&L from those trades.

Subscription sales, software licensing, analytics customers, signal sales, sales funnels and recurring customer revenue are OUT OF SCOPE, not alternative income routes. Their earlier inclusion was an assistant planning error. They must not return as fallback work when trading research is blocked. Reports and dashboards exist to observe and control the trading system, not to create a separate business.

Profit is the objective, not an established result. Research, historical replay, unseen evaluation, shadow and paper execution are stages towards this automated trader. A research report or a paper balance is not actual account income. No live adapter, funded account or profitable model is activated or claimed by this document.

## 2. Required trading loop

1. Ingest permitted price, session, macro/news and relevant cross-market observations with their actual availability times.
2. Build causal market state and obtain eligible specialist proposals. Course-derived and learned representations remain candidates subject to validation.
3. Select LONG, SHORT, PASS or WAIT with an explicit reason and expiry. Keep data-insufficient states separate from a directional opinion.
4. Apply deterministic pre-trade risk, exposure, cash/margin, spread and order-validity checks. Model confidence cannot override a rejection.
5. Submit through a mode-specific execution adapter: replay first, then shadow/paper, and only later an independently enabled broker adapter.
6. Reconcile acknowledgement, partial fills, rejection, cancellation and position state. Retries must not duplicate an order. A timeout does not establish that an order was not filled.
7. Manage open positions under their registered strategy and independent risk rules: protective exits, time/structure invalidation and any validated staged targets or breakeven actions. Unknown course parameters remain unknown.
8. Close/reduce positions and reconcile fills, balance, equity and realized/unrealized P&L. Persist sufficient state for recovery without reopening the same trade after restart.

LONG/SHORT describes the position objective; BUY/SELL describes an order side. A BUY may open a long or close a short. Reversing a position requires a tested reconciliation policy, not simply changing the side label. Entry PASS does not stop management of a position already open. A global stop policy must separately specify stopping entries and managing existing exposure.

These are target requirements. The present replay and decision seeds implement only part of this lifecycle; their existence does not establish a working broker loop.

## 3. What the financial report must measure

| Measure | Required separation |
| --- | --- |
| Closed-trade net P&L | Long versus short; strategy/version; instrument; actual versus simulated; account currency |
| Open exposure and equity | Marked-to-market unrealized P&L, outstanding orders, reserved margin and position age |
| Trading frictions | Spread once, commissions, slippage, financing/rollover and conversion timing; no double subtraction |
| Risk | Drawdown, loss streaks, recovery time, exposure and limit violations; not just win rate |
| Cash movements | Deposits, withdrawals, realized P&L and balance adjustments are distinct |
| Attribution | Dataset/fill source, model/strategy version, timestamps, run mode and reconciliation evidence |

For a reconciled account period, equity change less deposits plus withdrawals is the trading/account result only after separately accounting for external adjustments and the chosen fee/tax treatment. The ledger must document that treatment. Withdrawals are cash transfers, not new trading profit. The same equation must not mix currencies or realized balance with open-position equity.

Every profit estimate must be derived from valid measured outcomes and stated assumptions. Do not manufacture a monthly return, prescribe leverage to meet an income target, or turn arbitrary sample capital into an owner commitment. Report losing periods and uncertainty alongside positive results.

## 4. Readiness for actual trading income

| Stage | Required evidence | What can be claimed |
| --- | --- | --- |
| Correct replay and data | Causal features, correct long/short execution and account arithmetic, byte-linked provenance | The simulation behaves as specified |
| Specialist/Core evaluation | Nested selection, untouched evaluation, matched costs and explicit risk | Limited out-of-sample evidence; not actual earnings |
| Shadow/paper loop | Measured latency, rejects/partial fills, stop/restart behavior, position reconciliation and stale-data handling | Operational test evidence; paper P&L remains simulated |
| Separately authorized live pilot | Named account, permissions, exposure/loss limits, monitoring and rollback | Actual fills and realized gains or losses can be measured |
| Evidence-led expansion | Stable performance and operational evidence under new conditions | Expand instruments or capacity only after revalidation |

No date in the development calendar guarantees the first profitable month. Failure to find sufficient edge is a valid research outcome, not a reason to invent results or sell an unrelated product. Live activation is a later deployment decision; it is not forbidden as the final product goal, but it is not authorized in the current development step.

## 5. Planned work and owner inputs

Issue #45 owns trading-profit/risk measurement. R03 records account-currency and income-goal assumptions; G23 reconciles long/short realized and unrealized results; R08 specifies automated position-management and risk acceptance. All sales/customer work is removed. The former R07 sales slot is reassigned to the course-evidence/Market Grammar research design under #38.

Capital, account currency, acceptable loss/drawdown, per-trade risk, concurrency, leverage, income goal and withdrawal/reinvestment choices remain UNSET until deliberately established. A teacher's confidence or confluence count does not supply these controls. Keep financial account details private. Missing owner inputs do not prevent independent code/data research, but they do prevent unbounded live sizing.

This correction does not purchase services, open an account, use credentials or enable live orders. Existing tests, permissions and release gates remain in force.
