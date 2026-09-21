# Daily delivery plan

Version 1.1 | 22 September-21 October 2026 | Calendar basis: UTC

## How to use this plan

This is the concrete daily allocation beneath the handbook, not a claim of 30 days of automatic execution. Each date has a primary deliverable and one bounded research slot. The next three days are near-term; later days are reviewed weekly. A target date does not make an unfinished prerequisite complete. Original dates remain visible after carryover. The existing immutable planning/tasks.json is unchanged.

At the first actual run each day: inspect current GitHub work and the prior receipt; reconcile delivery_state.json; select dependency-ready work by priority; name the real executor. At the last actual run: record output/evidence, review/integration state, blockers, carryover and next action. Report a missed original date rather than restarting the plan. These instructions use the existing coordinator, not a new timer or paid agent.

## Dated work calendar

The rows are intended work windows, not promises to complete large features in one day. Existing bugs and sample access can move later work. Actual implementation and release gates override the nominal row.

| Day / UTC date | Primary product delivery | Research / revenue slot |
| --- | --- | --- |
| 01 / 2026-09-22 | G01 (P1, #39): Revalidate the pending execution fixes | R01: Resolve permitted data access and sample conditions |
| 02 / 2026-09-23 | G01 (P1, #39): Integrate verified fixes or record the exact gate | R01: Complete the source-access assessment |
| 03 / 2026-09-24 | G02 (P1, #43): Reproduce future-data-dependent entry decisions | R03: Record income goals and assumptions without invented inputs |
| 04 / 2026-09-25 | G02 (P1, #43): Fix and verify entry causality | R02: Reconcile the fifteen family definitions |
| 05 / 2026-09-26 | G03 (P1, #46): Reproduce incomplete opening-range errors | R02: Write initial source-grounded family cards |
| 06 / 2026-09-27 | G03 (P1, #46): Verify full range and timezone handling | R02: Identify overlapping variants and required data |
| 07 / 2026-09-28 | G04 (P2, #42): Review week-one evidence and replan if needed | R02: Publish canonical family/card decisions |
| 08 / 2026-09-29 | G05 (P2, #41): Prevent research from invoking the legacy coder | R04: Register temporal selection and search rules |
| 09 / 2026-09-30 | G06 (P1, #40): Tie import metadata to parsed bytes | R04: Define within-family and cross-family folds |
| 10 / 2026-10-01 | G07 (P1, #40): Record forecast provenance and availability | R04: Fix the trial/search budget before experiments |
| 11 / 2026-10-02 | G08 (P1, #40): Define account-currency and risk test vectors | R05: Check point-in-time macro/news sources |
| 12 / 2026-10-03 | G09 (P2, #37): Validate one permitted real-price sample | R05: Verify first actual, forecast and revision fields |
| 13 / 2026-10-04 | G10 (P2, #42): Replay three experts on the verified sample | R05: Mark unavailable or imprecise sources ineligible |
| 14 / 2026-10-05 | G11 (P2, #42): Reproduce outputs and measure one run | R05: Publish source-eligibility evidence |
| 15 / 2026-10-06 | G12 (P2, #38): Implement the family/eligibility registry | R06: Complete exact strategy-card rules |
| 16 / 2026-10-07 | G13 (P2, #38): Implement one missing technical family | R06: Verify its source and bounded parameters |
| 17 / 2026-10-08 | G14 (P2, #38): Implement a contrasting technical family | R06: Check expiry, invalidation and native exits |
| 18 / 2026-10-09 | G15 (P2, #38): Build bounded within-family comparison records | R06: Finish fifteen cards, with unknowns explicit |
| 19 / 2026-10-10 | G16 (P1, #40): Test purging and temporal split boundaries | R07: Evaluate the optional analytics customer/problem |
| 20 / 2026-10-11 | G17 (P2, #38): Run a small eligible development comparison | R07: Draft price and demand hypotheses, not sales claims |
| 21 / 2026-10-12 | G18 (P2, #38): Review redundancy and missing family coverage | R07: Define a bounded future validation experiment |
| 22 / 2026-10-13 | G19 (P2, #38): Compare deterministic Core and frozen baselines | R07: Assess distribution/support implications |
| 23 / 2026-10-14 | G20 (P2, #38): Prepare temporal out-of-sample training records | R07: Keep or reject the optional commercial route hypothesis |
| 24 / 2026-10-15 | G21 (P2, #38): Specify the first learned-Core experiment | R08: Link evidence to the income-readiness gates |
| 25 / 2026-10-16 | G22 (P2, #42): Test freshness and interrupted-run recovery | R08: Separate returns, withdrawals and product revenue |
| 26 / 2026-10-17 | G23 (P2, #45): Reconcile revenue assumptions with actual evidence | R08: Revisit capital and income inputs still missing |
| 27 / 2026-10-18 | G24 (P2, #42): Freeze the research-alpha candidate | R08: Publish the conditional revenue-readiness note |
| 28 / 2026-10-19 | G25 (P2, #42): Execute clean-environment alpha acceptance | R09: Audit claims and final-test prerequisites |
| 29 / 2026-10-20 | G26 (P2, #42): Fix acceptance failures or document blockers | R09: Verify holdout and evidence labels |
| 30 / 2026-10-21 | G27 (P2, #42): Publish alpha verdict and next-month backlog | R09: List remaining full-system requirements |

## Evidence and task state

Each delivery record contains a stable ID, clear title, priority, lane, linked GitHub item, original planned dates, dependencies, responsible function and acceptance output. Actual executor stays UNASSIGNED until a real run accepts the work. State is separate from the immutable plan: QUEUED, WORKING, REVIEW, BLOCKED, DONE or CANCELLED. DONE requires actual completion time and evidence references. A cancelled prerequisite is not completed. A reference being present is not proof that its content was verified.

R01 may produce an access assessment even when access is blocked, but its delivery state must remain BLOCKED until permission/access is actually verified; G09 cannot proceed on a document-only claim of permission. G08 identifies accounting requirements; any remaining account/execution P1 relevant to a comparison must be fixed before G10/G17 evaluation. The daily preview does not override these substantive gates. Weekly status review happens even if a planned product milestone misses its date.

## Unexpected issues and replanning

1. Check for an existing issue before adding a new INC identifier. Record priority, affected task, evidence, scope and dependency. Use a clear [P1]-[P4] [Bug]/[Task] title; preserve existing machine prefixes.
2. For a P1, contain the unsafe path and request a safe-checkpoint interruption of lower-priority work. Do not kill a worker, overwrite files or bypass checks to meet the clock.
3. Keep at most one product item and one research question active. Move the displaced item back to the queue with original dates and a reason. Keep 20% of initial capacity unallocated for correction/review.
4. Do not repeatedly retry an unchanged access blocker. Advance independent ready work and name the dependency. Review the next three days after each material incident, and later days at the weekly checkpoint.
5. Adding an incident to the plan does not authorize spending, secrets, external outreach or trading. An unplanned task can be appended with the same schema and unplanned=true; no daily-row rewrite is needed for priority selection.

## Read-only daily preview

For the coordinator or an authorized runtime, not a required owner chore:

    python scripts/plan_day.py --date 2026-09-22

The preview returns nominal work, selected dependency-ready IDs, blocked items, original-date misses, possible safe interruption and snapshot age. It never launches, commits, changes state, sends Telegram messages or verifies remote evidence. The coordinator must validate real source state before acting. No /today Telegram command is claimed by this change.

Initial preview for the first planned date selects G01 / PR #39 and R01 / issue #37 from an empty execution ledger. This is a preview, not evidence either worker started.

## Receipt and review format

Use: UTC date; selected IDs; actual executor/run mode; input revision; action; artifact/test evidence; review attribution; merged/deployed state; original target; revised estimate and reason; next task. Update handbook/status only for changed facts. Monthly revenue discussion follows issue #45 and REVENUE_PLAN.md, not expense-cap tables.

## Immediate GitHub work

Existing #39, #43, #37, #41, #40, #38 and #42 are reused. New #45 records revenue validation; #46 isolates the incomplete-session-range defect. Later records are concrete planned deliverables attached to their existing epic; create a separate child issue only when its scope is ready, instead of flooding GitHub with 30 speculative tickets.
