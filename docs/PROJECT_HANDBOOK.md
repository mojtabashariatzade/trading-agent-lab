# Trading Agent Lab
## Autonomous trading system: project handbook and delivery plan

Version 1.2 | Planning baseline: 22 September 2026 | Owner: project owner

Document custodian: Arman delivery function. Role names identify responsibilities, not independent people or continuously running agents. GitHub evidence remains authoritative for implementation and deployment status.

### Reading guide
Read sections 1-4 for direction and delivery, 5-8 for team/research/engineering, 9-10 for trading profit and risk, and 11-13 for release, operations and documentation. [REVENUE_PLAN.md](REVENUE_PLAN.md) defines income from trading; [DAILY_DELIVERY_PLAN.md](DAILY_DELIVERY_PLAN.md) lists dated work. [MARKET_GRAMMAR_DESIGN.md](architecture/MARKET_GRAMMAR_DESIGN.md) is the versioned review of the supplied course/market-representation proposal. The Persian guide describes the same scope. Dates are planning windows, not guarantees.

## 1. Executive decisions

Build an autonomous trading system for the owner's account. The intended operating loop is market observation -> eligible LONG/SHORT or PASS/WAIT decision -> deterministic risk and sizing -> execution -> position management and exit -> reconciled net trading P&L. The income objective is profit from the system's own trades, not selling access to the system.

Subscription sales, customer analytics, software licensing and signal-selling businesses are OUT OF SCOPE. Their inclusion in version 1.1 was an assistant planning error and has been removed from the active roadmap, financial plan and work queue. Reports, metrics and Telegram exist for the owner to inspect and control trading operations.

GBPJPY/M15 is the first benchmark, not a permanent product boundary. Candidate strategies compete within families; eligible family representatives compete across families; the Trading Decision Core uses only validated, available specialist evidence. Technical, fundamental and news information remain in scope. No candidate is presumed profitable. The software-development coordinator and Trading Decision Core are separate.

Research, historical replay, unseen evaluation, shadow and paper are delivery stages toward the autonomous trader, not alternative products. The first bounded milestone remains a reproducible real-data replay with the existing three experts after relevant execution/provenance defects are fixed. It does not replace the full fifteen-family and learned-Core objective.

Management decisions:
- Keep one active product-code item and one bounded research question; do not add agents or services merely to increase apparent activity.
- Finish a reviewed change or record its exact release blocker before starting overlapping implementation.
- Measure reconciled trading results and risk; do not substitute arbitrary return promises or sales metrics for performance.
- Treat one month as a conditional research-alpha target, not a promise of a complete trained/live system.
- Preserve negative results and uncertainty. NO_EDGE or DATA_INSUFFICIENT is a legitimate result, not a reason to force a trade.
- Build toward automatic position execution, but do not enable a broker, live orders, funding or increased risk in this documentation change. Later deployment needs its own validation and authorization.

Immutable tasks, repository protections and deployment configuration are not changed by this plan. Issue #42 owns reconciliation of historical runtime/approval descriptions with actual authorized development behavior. Routine owner authorization does not bypass platform permissions or required reviews.

## 2. Evidence baseline and current gaps

Repository inspected for this correction: main@72dd7dfe7fcf98e2d12d87e39e4686f2e21277e9. Product-code baseline remains 16bcf1f1fe39d76eca510734a20d267ad651871d; subsequent published changes added documentation and the daily planning preview. This is a dated snapshot, not a real-time dashboard.

| Area | Evidence-backed baseline | Remaining gap |
| --- | --- | --- |
| Research components | Bars, execution, three experts, synthetic tournament, fundamental schema and import contracts exist | Full product acceptance is not established |
| Execution corrections | PR #39 remains open | Revalidate its current head/base and integrate or state the actual gate |
| Entry causality | #43 identifies future-execution-data dependence | Before-fail/after-pass regression and correction |
| Session range | #46 isolates incomplete opening ranges | Timestamp-based completeness and timezone tests |
| Real history | #37 records access, permission and coverage questions | Authorized sample and metadata derived from actual bytes |
| Fifteen families | #38 defines the intended competition | Canonical registry, implementations and nested temporal selection |
| Course / Market Grammar | Owner supplied a research proposal | Versioned design only; no imported course dataset or trained universal model |
| Research execution | #41 records local routing to a disabled coding path | Research-capable executor or verified read-only report handoff |
| Unattended delivery | #42 requires actual scheduled receipts | Enabled scheduling alone does not prove productive execution |
| Telegram with PC off | PR #29 is still a proposal | Safe private handling, authenticated state and tested consumer handoff |
| Automatic market operation | Seed directions and fixture replay exist | Complete tested order/position/recovery adapter before operational use |

Keep distinct: code written, acceptance passed, CI passed, reviewed, merged and deployed. Also separate STRUCTURE_PASS, SOURCE_VERIFIED and EXPERIMENT_VALIDATED. The current system does not establish actual trading earnings, a trained universal representation or a live deployment. Account capital, currency, risk limits and withdrawal choices remain UNSET unless deliberately supplied.

## 3. Short-term delivery: first 30 days

The original calendar remains 22 September-21 October 2026 UTC. Planned dates are not worker start times. Record actual starts separately; never reset Day 1 to hide a delay. The full schedule is in DAILY_DELIVERY_PLAN.md and planning/delivery_plan.json.

| Window | Outcome | Acceptance / checkpoint |
| --- | --- | --- |
| Days 1-3 | Resolve a bounded execution/correctness item | #39 release decision; #43 regression or exact blocker |
| Days 4-7 | Validate session completeness and source path | #46 tests; authorized sample/access decision; revise forecast from actual capacity |
| Days 8-14 | Deliver a three-expert real-data vertical slice | Reproducible proposals, long/short trade outcomes, account effects and manifest |
| Days 15-21 | Establish competition and representation contracts | Family/variant/data eligibility, nested splits and bounded course/Grammar design |
| Days 22-30 | Test a research-alpha candidate | Clean replay, net P&L/risk report, known limitations and remaining final-system work |

Independent research may proceed while code or access is blocked: source rights, point-in-time data, strategy cards and course-provenance design. Performance ranking cannot proceed without its integrity/data gates.

The base alpha target includes corrected replay, a permitted sample, auditable results, the fifteen-family specification and eligible baseline comparisons. Full history, all news specialists, learned Market Grammar and a trained neural Core are not assumed day-30 deliveries. Course extraction continues separately; this plan does not turn incomplete lessons into executable rules.

At week one, absence of an authorized sample/access decision, measured run or demonstrated delivery path requires an explicit date/scope revision. A reduced alpha must not be called the complete trading system.

## 4. Medium- and long-term roadmap

| Horizon | Deliverable | Promotion gate |
| --- | --- | --- |
| Days 31-60 | Expand eligible families and reproducible historical ingestion | Rights/coverage, causal features, bounded trials and nested selection |
| Days 61-90 | Compare deterministic and learned Core candidates | Temporal out-of-sample predictions, matched costs/risk and measured incremental value |
| Months 3-6 | Test order/position lifecycle in shadow and paper modes | Long/short sizing, protective exits, rejects/partial fills, stop/restart and reconciliation |
| Months 6-12 | Conditional multi-market operation and a limited authorized live pilot | Per-market validity, portfolio exposure, actual risk/operational evidence and explicit activation |

These are review horizons, not promised dates for profit. The full product is intended to place and manage trades automatically after the deployment gates; the present research stage is not a permanent prohibition on that goal.

Growth is into instruments, regimes, timeframes and validated trading capacity, not a separate sales business. Keep the first benchmark reproducible before adding markets. Instrument identity is required for execution/risk even when withheld from a representation experiment. Register instrument-specific contract size, currencies, sessions and execution costs; do not reuse GBPJPY thresholds blindly.

The proposed research sequence in MARKET_GRAMMAR_DESIGN.md preserves phases 0-10: ongoing course extraction, integrity fixes, ontology, teacher reconstruction, empirical course tests, universal prototype, leave-one-market-out evaluation, Classic/Course/Universal/Combined comparison, Core, portfolio and shadow/paper. These additions do not silently compress all research into the first month.

## 5. Delivery queue and ownership

Reuse existing issues. Split only the next necessary independent deliverable; do not flood the backlog with speculative tasks.

| Order | Work | Responsible function | Evidence |
| --- | --- | --- | --- |
| 1 | Resolve PR #39 | Coordinator + development/review | Exact head/base checks, review and merge or exact gate |
| 2 | Entry causality, #43 | Kian / Negar | Removing future data cannot rewrite an earlier entry |
| 3 | Source path, #37 | Saman | Source-specific permission/access decision and valid sample |
| 4 | Session completeness / research routing, #46 / #41 | Development / QA | Bounded regressions and actual handoff behavior |
| 5 | Remaining integrity, #40 | Quant/data/development | Tested timing, provenance and account invariants |
| 6 | Families and representation, #38 | Parsa / Niloofar | Canonical family rules and versioned course/Grammar research |
| 7 | Trading P&L and management, #45 | Quant / development | Long/short fills, risk and account reconciliation |

The 36-record daily calendar retains its IDs and original dates. R07 is reassigned from the withdrawn sales task to course provenance and Market Grammar design under #38. R03, R08 and G23 now concern only the trading account, position management and P&L. Record this scope revision; never imply that changing a task title completed it.

The owner controls objectives, funding, nonroutine access and future live activation. Arman coordinates ready work and release decisions. Kian implements and supplies tests. Negar performs a recorded review step; if the same assistant does both, label SELF_REVIEW. CI is independent execution, not independent engineering judgment. Saman checks data/provenance; Niloofar checks macro/news timing; Parsa checks hypotheses/selection. Raha reports actual evidence/freshness. Names alone do not establish parallel workers.

Definition of Ready: concrete behavior, scope, input evidence, dependencies, test oracle and an actually capable executor. Definition of Done: acceptance, current required CI, honest review attribution, applicable integration evidence and updated documentation. Parent epics retain unresolved work; local deployment needs its own receipt.

## 6. Research, course knowledge and fifteen-family competition

Retain original S01-S15 identifiers until #38's taxonomy is explicitly reconciled: EMA trend; Donchian; volatility compression; session breakout; trend pullback; RSI reversion; Bollinger re-entry; failed breakout; multi-timeframe alignment; currency strength; rate/yield context; UK surprise; Japan surprise; central-bank statement change; reversal after news shock. All start UNTESTED. Related variants are not automatically independent sources of evidence.

Each card specifies exact entry/exit, invalidation, expiry, session/timezone, version, required data, missing-data behavior, source and bounded parameters. Preserve signal/common-exit, native-system and account/Core leagues. The common signal contract uses ATR14 stops, 3R targets and 240 real minutes; fixture defaults are not proof of that implementation. Course trade management belongs to the native strategy, not a post-hoc unrelated adjustment.

Tune variants, select family representatives and choose the cross-family set inside allowed temporal development folds. Freeze before outer evaluation. Train learned selectors on temporal out-of-sample specialist predictions. Do not tune on final holdout. Start with a registered modest variant budget, benchmark it and count every discarded trial. Report uncertainty, downside co-loss, redundancy, costs and incremental contribution; no forced family champion.

The attached proposal adds a candidate Geometry -> Market State -> structured Confluence -> Decision Core path. The course remains an Expert Knowledge Layer. Preserve video/time/transcript/frame provenance, UNKNOWN and CONFLICTING evidence, and TEACHER_CLAIM -> FORMALIZED_HYPOTHESIS -> EMPIRICALLY_VERIFIED. Teacher confidence and the number of confluences are not calibrated probabilities or fixed trading rules.

Test teacher-reconstruction accuracy separately from market validity. Compare A Classic Specialists, B Course Knowledge, C Universal Market Dynamics and D Combined. Add prespecified leave-one-instrument-out AND temporal isolation, causal normalization, identity-leakage controls and per-market reporting. Universal is a hypothesis, not an assumed winner. These are design requirements, not completed ingestion, training or experiments.

Macro/news remain essential context or specialists where data permits. Preserve first actual, pre-release forecast observation, revisions and availability precision. Forex Factory is a secondary cross-check, not proof of archived point-in-time forecasts. Missing information means ineligibility or abstention, never invented numbers.

The Core must choose when not to enter. Managing an already-open position remains active under registered risk rules even if new-entry output is PASS. Small neural, reinforcement and fly-inspired models remain candidates; complexity must add measured value.

## 7. Engineering and scalability

Prefer a modular application with separate ingestion, immutable data, causal geometry/features, proposals, replay, selection, risk, execution adapters, position management and account reporting. The development coordinator stays outside trading authority. Do not replace working modules with a broad rewrite for this design.

The eventual lifecycle must distinguish position intent from order side: BUY can open a long or reduce a short. Handle fills, partial fills, rejects, cancellation, protective orders, safe reversal and duplicate suppression explicitly. Reconcile pending orders/positions after disconnect or restart before opening new exposure. A missing acknowledgement is not evidence an order never filled.

Record event, available, decision-ready and fill times. Confirmed swing events become usable at confirmation time, not their retrospective chart location. Spread is counted once; commission, slippage, rollover, account currency conversion, quantity and margin remain explicit. Unknown daily loss, sizing and maximum trade limits are configuration/design blockers, not inferred course rules.

Keep immutable raw, processed, fixture and holdout stores distinct. Bind metadata to parsed bytes. Keep course media and account/private data out of the public repository; source summaries do not authorize raw-data redistribution. An ignored file is not a backup.

Profile before optimization: parse once, cache causal arrays, avoid growing-prefix copies and repeated EMA rescans, and bound independent family/fold workers. Cache keys include data/code/parameter/cutoff versions. Prove optimized/reference parity. Scale compute or storage only for a measured bottleneck and the applicable permission; do not silently provision a service.

## 8. Capacity, scheduling and progress

Keep original dates, queue age, active time, blocked time and revised estimates separate. Two no-output runs on the same item require a capability diagnosis, not another agent or prompt rewrite.

| Priority | Checkpoint after actual start | Small scoped verified-fix target |
| --- | --- | --- |
| P1 | 5 minutes | 1 elapsed hour |
| P2 | 30 minutes | 4 elapsed hours |
| P3 | 4 hours | 24 elapsed hours |
| P4 | 24 hours | 72 elapsed hours |

These are planning targets, not guaranteed response times. Hourly scheduling cannot guarantee five-minute detection. Larger tasks need a separately estimated deliverable. Waiting on CI/access does not erase the original target.

At the first actual daily run, reconcile prior receipts and current GitHub evidence; inspect the nominal row and choose safe dependency-ready work. Retain unfinished work across dates. Advance early when ready, rather than waiting for an artificial date. At each completed work run record action, output, real tests, actual actor/mode, input/output SHA, review, merge/deployment, blocker and next step.

planning/delivery_plan.json is the task plan; planning/delivery_state.json records actual receipts. scripts/plan_day.py is a read-only consistency preview, not a worker or authority to trade. Verify its referenced evidence before acting. Active and completed fields must not be filled merely to make the dashboard look busy.

Deduplicate new incidents, assign clear P1-P4 titles and link affected work. A P1 may request interruption at a safe checkpoint; do not forcibly overwrite concurrent state or bypass tests. Carry displaced work with original dates. Keep the initial 20% correction/review buffer, review the next three days closely and later dates weekly. These capacity figures are planning assumptions, not measured throughput.

Measure delivered fixes, reopenings, review wait, data coverage, reproducibility, experiment resource use and account/risk evidence. Do not count sales activity, renamed issues or heartbeat volume as progress on this trader.

## 9. Income from the system's own trades

The only income mechanism in scope is net P&L from the system's LONG and SHORT positions. See REVENUE_PLAN.md and #45. The previous customer/pricing route and numerical sales scenarios are removed. The zero-expense table stays removed as requested.

Financial reporting must show realized and unrealized account-currency P&L, trading frictions, exposure, drawdown, recovery and cash flows. Distinguish actual fills from replay/paper results. Deposits are not earnings, and withdrawals are not additional profit. Net outcomes must reconcile with the chosen account ledger and cost treatment.

Do not invent monthly yields, owner capital, maximum loss, leverage or a first-income date. Assess positive, flat and losing periods from valid evidence. Capital/currency, income objective, risk limits and withdrawal/reinvestment choices remain deliberate inputs. Their absence need not block unrelated engineering, but does block unbounded live sizing.

The path is correct data/replay -> valid specialist/Core selection -> tested shadow/paper lifecycle -> separately authorized live pilot -> measured gains OR losses -> evidence-led expansion. Profit is the objective, not a guaranteed deliverable. No new source of revenue is substituted if the strategy lacks an edge.

R03 specifies trading-account assumptions; G23 reconciles long/short account results; R08 defines automated trade-management/risk acceptance. R07 serves the course/Grammar design. None is a purchase, credential or live-activation authorization.

## 10. Risk, privacy and continuity

| Risk | Trigger | Response / owner function |
| --- | --- | --- |
| Invalid outcomes | Future-data or accounting defect | Contain affected evaluation; quant/QA regression; #40/#43 |
| Missing or restricted data | Unresolved access/coverage | Source-specific decision or alternative; Saman; #37 |
| Unsupported research approval | Shape check mistaken for truth | Separate source/empirical evidence; #41/#42 |
| Unproved unattended work | Run without deliverable | Capability diagnosis and actual receipt; Arman |
| Private data exposure | Public mailbox/media/account data | Private evidence references, least privilege and authenticated state |
| False diversity or transfer | Correlated variants or identity leakage | Nested selection, ablations and per-market controls; #38 |
| Duplicated or unmanaged exposure | Restart, lost acknowledgement, partial fill | Idempotent order/position reconciliation and protective policies |
| Resource exhaustion | Registered workload exceeds capacity | Bounded jobs, checkpointing and reviewed resource decision |
| Income overclaim | Assumed return presented as an earning | Separate objectives, simulations and actual reconciled results; #45 |
| Operational dependence | Lost session or powered-off machine | Persisted receipts, explicit deployment revision and restore drill |
| Stale documentation | Changed behavior without source revision | Update relevant sections; mark REVIEW_REQUIRED |

No jurisdiction is inferred from approximate location. Before future broker/data use, establish actual account eligibility and applicable terms. This is a requirements register, not a legal opinion. Keep credentials outside code, prompts and logs. Untrusted PR code must not run with broker or bot secrets. Role names and comment markers are not authentication.

Back up accepted checkpoints and immutable data/model manifests to approved independent storage, and test restore. A second folder on one disk is not independent recovery. If safe storage is missing, state the limitation. Measure recovery time from a drill; do not invent an availability guarantee.

## 11. Final-test and operational acceptance

Distinguish software correctness from evidence of a trading edge. A technically valid run may conclude NO_EDGE. Freeze code/environment, data rights/checksums, candidate/model versions, parameters, cost/account rules, metrics, exclusions and stop conditions before final evaluation. Record every prior look at the holdout; once it influenced design it is no longer untouched.

Required gates:
- No unresolved P1 in the evaluated path; current tests and honest review satisfy repository rules.
- Causal feature/forecast/entry timing; absent future data cannot rewrite an earlier entry.
- Parsed-byte provenance; course/fixture/evaluation evidence cannot be silently mixed.
- One explicit account/execution convention, with both long and short paths, costs, overlap and censoring.
- Clean-environment decision/trade replay is reproducible within predeclared numerical tolerances.
- Selection, transforms and calibration use only allowed development evidence.
- Teacher reconstruction, predictive validity, paper performance and live P&L have distinct reports.
- PASS/WAIT and risk veto work; existing position management is not disabled by an entry abstention.

The final package contains a frozen manifest, documented entry point, registered experiment, audit records, baseline/ablation comparisons, uncertainty and cost stress, resource measurements and known limitations. A one-command final run remains a deliverable to implement, not an existing capability claimed by this document.

Shadow/paper acceptance adds actual order/position lifecycle, stale-data protection, partial-fill/reject/duplicate handling, emergency stop and restart/reconciliation tests. Only a separately authorized deployment enables live orders. Current design changes do not perform that deployment.

## 12. Operations and truthful status

Research must progress independently of Telegram when safe. Telegram is a monitoring/control interface, not an alternate source of truth or the trading engine. Do not let local and cloud consumers poll one bot without a verified handoff; do not reset offsets/webhooks blindly.

Report source revision, observation time, last actual successful delivery and stale/blocked state. GitHub main and local deployed revision are different fields. A merge is not a Windows installation. Keep private conversation separate from public evidence.

Scheduling, connectivity and permissions limit current automations. A current chat or enabled task is not proof of continuous coding or a running trading service. Respect owner pause/stop and permission blocks. Preserve incident evidence, contain unsafe work, identify the last good checkpoint, make a scoped correction and verify it. Notify material changes, not repeated unchanged heartbeats.

## 13. Living documentation and change control

Reading path: README -> this handbook -> trading-profit plan, daily plan, Market Grammar design and evidence/contracts. Status JSON is a dated, non-executable snapshot. Word exports are fixed reading copies; GitHub history is the versioned record.

The substantive-change author updates affected interfaces, assumptions, acceptance, trading P&L/risk or operations in the same reviewed change, or links a bounded follow-up. Safety-critical missing documentation blocks release. Do not regenerate the whole plan on heartbeats or postpone ready fixes to reformat documents.

After verified merges, source results and deployments, update changed status fields only. At the next real weekly review summarize deliveries, blockers, actual capacity and trading-readiness evidence. More than seven days without reviewing the overview means REVIEW_REQUIRED. Historical evidence remains valid only for its recorded version.

Versioning: patch for factual corrections, minor for compatible scoped design additions, major for a new architecture/acceptance contract when adopted into implementation. This v1.2 restores the owner objective and adds a proposal; it does not implement a new trading architecture or change immutable runtime gates.

Decision register:
- D01: the three-expert real-data slice is intermediate, not the complete system.
- D02: retain S01-S15 until an explicit taxonomy decision.
- D03: trading P&L is the sole income scope; withdraw the unrelated sales route.
- D04: one active code item and one bounded research question; no fictitious agents.
- D05: label self-review and require actual unattended-work receipts.
- D06: distinguish current main, historical evidence and local deployment.
- D07: runtime/policy reconciliation remains #42, not a document-side permission change.
- D08: preserve the original daily calendar and carryover evidence.
- D09: adopt the course/Market Grammar proposal as a research design, not proven behavior.
- D10: final capability is automated long/short position execution and management; live activation is a separate gate.

Change record: problem, evidence, proposal, affected data/behavior/risk, alternatives, acceptance/rollback and actual implementation reference. Work receipt: time, task, actor/mode, SHA, action/output, tests, review, integration/deployment, blocker, next step.

Changelog 1.2: removed all active sales/customer tasks and revenue routes; clarified automated LONG/SHORT lifecycle; reassigned R07; added versioned course/Grammar design while retaining classic families and integrity gates. Earlier revisions remain in Git history, not active work. This publication does not fix the open runtime defects, train a model or deploy a trader.

## 14. Source register

The owner-supplied Market Grammar proposal is the source for the new research framing, not evidence that course claims are verified. Its raw media were not imported in this change. Engineering refinements and unresolved conflicts are labelled in architecture/MARKET_GRAMMAR_DESIGN.md.

Repository baseline: https://github.com/mojtabashariatzade/trading-agent-lab/commit/72dd7dfe7fcf98e2d12d87e39e4686f2e21277e9

Contract and work definitions: docs/PROJECT_CONTRACT.md and planning/tasks.json at that baseline. Decision/tournament seeds: trading_lab/contracts.py and trading_lab/tournament/core.py at that baseline.

Tracked evidence: PR #39; issues #37, #38, #40, #41, #42, #43, #45 and #46; proposed Telegram relay PR #29. Revalidate live issue/PR status before acting. None is evidence of this project's profitability.
