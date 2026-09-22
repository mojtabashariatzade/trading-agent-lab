# Daily delivery plan

Version 1.2 | 22 September-21 October 2026 | Calendar basis: UTC

## How to use this plan

The product is an autonomous LONG/SHORT trader for the owner's account. Income means net trading P&L. The former sales/customer work is withdrawn. This calendar is the concrete allocation beneath the handbook, not proof of continuous execution. Dates, task IDs and carryover history are retained. The next three days are near-term; later days are reviewed weekly. The immutable planning/tasks.json is unchanged.

At the first actual daily run, reconcile GitHub and previous receipts, select safe dependency-ready work and identify the real executor. At each completed run record output, tests, review/integration, blockers and next action. Carry unfinished work instead of restarting the calendar. If work finishes early, pull ready work forward rather than waiting for its nominal date. The existing preview is read-only, not a worker launcher or evidence verifier.

## Dated work calendar

These are intended work windows, not promised one-day deliveries. Actual integrity, access and release gates override the nominal row.

| Day / UTC date | Primary product delivery | Trading-research slot |
| --- | --- | --- |
| 01 / 2026-09-22 | G01 (P1, #39): Revalidate the pending execution fixes | R01: Resolve permitted data access and sample conditions |
| 02 / 2026-09-23 | G01 (P1, #39): Integrate verified fixes or record the exact gate | R01: Complete the source-access assessment |
| 03 / 2026-09-24 | G02 (P1, #43): Reproduce future-data-dependent entries | R03: Specify trading-account P&L and risk assumptions |
| 04 / 2026-09-25 | G02 (P1, #43): Fix and verify entry causality | R02: Reconcile the fifteen family definitions |
| 05 / 2026-09-26 | G03 (P1, #46): Reproduce incomplete opening ranges | R02: Write source-grounded family cards |
| 06 / 2026-09-27 | G03 (P1, #46): Verify range and timezone handling | R02: Identify overlapping variants and required data |
| 07 / 2026-09-28 | G04 (P2, #42): Review week-one evidence and replan | R02: Publish canonical family/card decisions |
| 08 / 2026-09-29 | G05 (P2, #41): Stop research invoking the legacy coder | R04: Register temporal selection and search rules |
| 09 / 2026-09-30 | G06 (P1, #40): Tie metadata to parsed bytes | R04: Define within-family and cross-family folds |
| 10 / 2026-10-01 | G07 (P1, #40): Record forecast provenance/availability | R04: Fix the search budget before experiments |
| 11 / 2026-10-02 | G08 (P1, #40): Define account/risk test vectors | R05: Check point-in-time macro/news sources |
| 12 / 2026-10-03 | G09 (P2, #37): Validate a permitted real-price sample | R05: Verify first actual, forecast and revision fields |
| 13 / 2026-10-04 | G10 (P2, #42): Replay long/short expert outcomes | R05: Mark unavailable or imprecise sources ineligible |
| 14 / 2026-10-05 | G11 (P2, #42): Reproduce outputs and benchmark | R05: Publish source-eligibility evidence |
| 15 / 2026-10-06 | G12 (P2, #38): Implement family/eligibility registry | R06: Complete exact strategy-card rules |
| 16 / 2026-10-07 | G13 (P2, #38): Implement one missing technical family | R06: Verify source and bounded parameters |
| 17 / 2026-10-08 | G14 (P2, #38): Implement a contrasting family | R06: Check expiry, invalidation and native exits |
| 18 / 2026-10-09 | G15 (P2, #38): Build within-family comparison records | R06: Finish cards with unknowns explicit |
| 19 / 2026-10-10 | G16 (P1, #40): Test purging and split boundaries | R07: Design video/time/transcript/frame provenance |
| 20 / 2026-10-11 | G17 (P2, #38): Run an eligible development comparison | R07: Separate teacher claims, unknowns and hypotheses |
| 21 / 2026-10-12 | G18 (P2, #38): Review redundancy and missing coverage | R07: Define causal geometry/state/confluence interfaces |
| 22 / 2026-10-13 | G19 (P2, #38): Compare Core and frozen baselines | R07: Specify teacher reconstruction versus market-validity tests |
| 23 / 2026-10-14 | G20 (P2, #38): Prepare out-of-sample training records | R07: Specify A/B/C/D and leave-one-instrument-out evaluation |
| 24 / 2026-10-15 | G21 (P2, #38): Specify learned-Core acceptance | R08: Define LONG/SHORT intents, sizing and risk-veto acceptance |
| 25 / 2026-10-16 | G22 (P2, #42): Test freshness and recovery | R08: Specify protective exits, invalidation and position management |
| 26 / 2026-10-17 | G23 (P2, #45): Reconcile net long/short P&L and exposure | R08: Define partial/rejected/duplicate fill and restart tests |
| 27 / 2026-10-18 | G24 (P2, #42): Freeze research-alpha candidate | R08: Publish the automated position-lifecycle/risk checklist |
| 28 / 2026-10-19 | G25 (P2, #42): Execute clean alpha acceptance | R09: Audit claims and final-test prerequisites |
| 29 / 2026-10-20 | G26 (P2, #42): Fix failures or document blockers | R09: Verify holdout and evidence labels |
| 30 / 2026-10-21 | G27 (P2, #42): Publish verdict and next-month backlog | R09: List remaining autonomous-trading requirements |

R07 now belongs to #38 and is P2 because the owner supplied a concrete trading-research direction. Its dependency is R02 rather than an income/sales question. Its design v0.1 is available in architecture/MARKET_GRAMMAR_DESIGN.md; the scheduled work validates and refines that design, not a claim of already importing course media or training a model. The original R07 dates and ID remain traceable. R03/R08/G23 are only about trading-account profit, risk and automated management.

## Evidence and task state

Each record retains title, priority, lane, issue, original dates, dependencies, responsibility and acceptance. Actual executor stays UNASSIGNED until a real run starts. QUEUED/WORKING/REVIEW/BLOCKED/DONE/CANCELLED are recorded separately from the plan. DONE requires completion time and evidence; the coordinator must verify the actual referenced content. Cancellation is not completion.

R01 stays BLOCKED if actual permission/access is unresolved; a written assessment alone cannot authorize G09. G08's test-vector specification does not close remaining account P1s. All relevant #40 timing/account/provenance defects must be fixed before G10/G17 evaluation. Existing daily-preview logic does not enforce those substantive acceptance decisions. The weekly review must still occur if milestones slip.

Course extraction remains independent of implementation. No arbitrary retest tolerance, swing rule, confluence count/weight, sizing or daily loss limit is inferred from incomplete lessons. Raw course evidence stays private and immutable. Classic families and macro/news remain in scope. Later multi-market training is not squeezed into the current alpha dates.

## Unexpected work and replanning

1. Deduplicate before adding an INC identifier. Record actual impact, scope, priority and dependency; preserve machine prefixes and original dates.
2. Contain an unsafe P1 and request interruption at a safe checkpoint. Do not kill processes, overwrite concurrent work or bypass tests to meet a date.
3. Keep one product item and one research question active. Carry displaced work forward. The initial 20% review/correction reserve is a planning assumption.
4. Do not repeatedly retry unchanged access failures; advance safe independent work. Review near-term dates after material incidents and later dates weekly.
5. A new task does not grant broker, live, data-purchase or credential authority. The product goal includes eventual automatic trading; activation remains a separate release step.

## Read-only preview and receipts

For the coordinator, not a required owner chore:

    python scripts/plan_day.py --date 2026-09-22

The preview reports nominal work, selected IDs, blocked dependencies, missed original dates, safe-interruption requests and snapshot freshness. It does not start workers, change state, authenticate evidence, send Telegram messages or place trades. No new /today command is claimed.

Record UTC time, IDs, actual executor/mode, input/output revision, action, artifacts/tests, review attribution, merge/deployment state, original target, revised estimate, blocker and next step. Update handbook/status only for changed facts. Keep scope changes distinct from task completion and live deployment.

Existing issues #37-#43, #45 and #46 are reused. No new speculative issues or agents are created for this correction. Sales, customer interviews, subscription pricing and software-revenue work are not part of this calendar.
