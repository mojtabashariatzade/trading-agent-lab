# Revenue model and path to income

Version 1.1 | 22 September 2026 | Owner-facing commercial decision record

## 1. What the project is trying to earn

The primary route is income from the owner's own trading capital, after the system demonstrates a repeatable edge and receives separate authorization for actual trading. The project must not be silently turned into a subscription business instead. A second, optional route is selling read-only research/analytics software after validating a genuine customer need. Licensing to a business is a later option; trading other people's money, copy trading and paid trade recommendations are not part of the currently authorized product.

This replaces the former expense/zero-budget table. Removing that table does not authorize purchases, account opening, brokerage access or Live activation. The remaining discussion of fees is necessary to distinguish revenue from profit, not a new expense budget.

## 2. Primary route: own-capital trading

Income depends on capital, a validated after-transaction-cost return distribution, drawdowns, operational reliability and withdrawals. Deposits are not revenue; unrealized gains and equity recovery are not automatically cash available to withdraw. Backtests and paper results are not actual earnings. Simulated performance can differ substantially from actual trading; the CFTC explicitly cautions against presenting simulations as actual performance. [1]

The following is an arithmetic sensitivity example, NOT a forecast, return target, likelihood estimate or recommended capital allocation. The returns are assumed after transaction costs but before operating charges and taxes. The losing case is not a worst-case loss limit. Larger losses are possible.

| Example account capital | Losing month -5% | Flat month 0% | Illustrative +0.5% month | Illustrative +1.5% month |
| --- | ---: | ---: | ---: | ---: |
| USD 10,000 | -500 | 0 | 50 | 150 |
| USD 50,000 | -2,500 | 0 | 250 | 750 |
| USD 100,000 | -5,000 | 0 | 500 | 1,500 |

Formula for the simplified no-flow scenario: monthly trading P&L = starting capital x net trading return. With deposits/withdrawals during the period, use time-weighted performance and separately reconcile cash flows instead of treating added capital as strategy gains.

For a desired withdrawal of USD 1,000 per month, the arithmetic capital requirement would be USD 200,000 at an assumed 0.5% monthly return or about USD 66,667 at 1.5%, before operating charges, taxes and reserve needs. Neither assumption is established for this system. If sustainable net returns are nonpositive, no capital amount solves the income target by this formula. Do not increase leverage or choose an optimistic assumed return just to make the required capital look smaller.

Track realized P&L, marked-to-market equity, fees, drawdown, longest recovery interval and withdrawals separately. A withdrawal/reinvestment policy and drawdown reserve must be chosen before relying on trading proceeds for recurring living expenses. A profitable month is not evidence of a salary-like income stream.

## 3. Optional route: a research and analytics product

Candidate offer: an auditable strategy-comparison workspace with experiment history, data-quality checks and explanatory reports, not promises of profitable signals. Intended early users are an unvalidated hypothesis: independent quantitative researchers and small teams that need reproducible comparisons. Decide whether they actually need it before building billing or a separate product team.

Illustrative pricing/customer combinations only; these are not sales projections or approved prices:

| Hypothetical paid subscribers | Hypothetical monthly price | Gross monthly recurring revenue |
| ---: | ---: | ---: |
| 10 | USD 29 | USD 290 |
| 30 | USD 49 | USD 1,470 |
| 100 | USD 79 | USD 7,900 |

MRR measures the monthly normalized recurring subscription component; one-off setup work is not recurring revenue. [2] Gross recurring revenue is not profit or collected cash: deduct refunds, collection/payment effects and the actual costs of delivery/support, and report taxes separately. Next-month revenue also changes with new, retained, downgraded and cancelled subscriptions.

Validation sequence: draft one customer/problem hypothesis; define a demonstrable read-only use case; collect explicitly authorized user feedback; test willingness to pay; seek a small paid pilot only after rights, billing and support readiness. A suggested discovery target is five qualified conversations and three users independently identifying the same problem. Those are proposed validation thresholds, not completed interviews or proof of demand. External outreach and sales require their own authorization.

Do not add hypothetical software revenue to hypothetical trading gains and present the sum as a company forecast. Each route needs separate evidence and accounting.

## 4. Revenue gates and commercial horizons

| Gate | Evidence needed | Income status |
| --- | --- | --- |
| Research alpha, first 30-day plan | Reliable data/replay, baseline comparisons and documented unknowns | Revenue hypothesis only; no promised payment date |
| Validated specialist/Core selection | Untouched evaluation, cost stress, stable account/risk behavior | Evidence for a pilot decision, not realized earnings |
| Shadow/paper validation | Observable execution, drawdown/recovery and failure/restart behavior | Simulation record, not revenue |
| Separately approved limited live use | Named capital, broker, risk/withdrawal limits and actual account reconciliation | First realized gains OR losses become measurable |
| Optional software pilot | Validated demand, data/IP rights, support and paid pilot approval | Only actual paid subscriptions count as sales |
| Expansion | Repeatable evidence, capacity, legal jurisdiction and unit economics | Scale only the route with demonstrated value |

The 3-6 and 6-12 month roadmap horizons are review windows, not promised dates for profit or product sales. Failure to establish an edge means revise or stop the trading-income route; a software product is not automatically a substitute unless separately validated.

## 5. Inputs and daily ownership

Issue #45 tracks this revenue work. Record, rather than guess: investable capital and currency; desired monthly net income; maximum tolerable drawdown; withdrawal versus reinvestment; applicable jurisdiction; and whether the optional software route is wanted. These inputs remain UNSET until supplied. Their absence does not stop unrelated engineering.

During the first week, R03 produces the assumptions register. G23/R08 revisit it using actual research evidence later in the plan. The owner selects income goals and capital/risk; the delivery coordinator links each revenue gate to actual product tasks; Parsa validates return/risk measurement; Niloofar/Saman validate data assumptions. No new independent commercial agent is implied.

Separate four dashboard fields: owner income goal, hypothesis/sensitivity, measured research result, and actual receipts/withdrawals. Each number needs a period, currency, evidence level and source. Do not populate a missing actual with a hypothetical example.

## References

[1] CFTC, trading-system and hypothetical-performance advisory: https://www.cftc.gov/sites/default/files/opa/enf00/opa4397-00.htm . Used only for the limitation of hypothetical results, not a claim about this project's future returns or a jurisdiction-specific legal opinion.

[2] Stripe, Monthly recurring revenue explained: https://stripe.com/resources/more/what-is-monthly-recurring-revenue . Used for the definition of MRR, not pricing or demand assumptions.
