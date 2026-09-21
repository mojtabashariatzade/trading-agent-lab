# Trading Agent Lab
## Project handbook and delivery plan

Version 1.0 | Planning baseline: 22 September 2026 | Owner: project owner

Document custodian: Arman delivery function. Role names identify responsibilities, not independent people or continuously running agents. This handbook is the project reading entry point. GitHub evidence remains authoritative for implementation and deployment status.

### Reading guide
Read sections 1-4 for direction and near-term delivery, 5-8 for team/research/engineering, 9-10 for finance and risk, and 11-13 for release, operations and documentation. The Persian companion is an owner-facing summary of this same plan, not a separate backlog. Proposed dates are planning windows, not delivery guarantees.

## 1. Executive decisions

Build a GBPJPY/M15 research system in which candidates compete within strategy families, eligible family representatives compete across families, and a Trading Decision Core selects a proposal or PASS. Technical, fundamental and news information are in scope. None of the fifteen candidates is presumed profitable. The software-development coordinator and Trading Decision Core remain separate. [R1, R7]

The immediate business objective is reliable evidence at controlled cost, not trading revenue. The first deliverable is a reproducible real-data replay with the existing three experts, after relevant execution and provenance defects are fixed. This is an intermediate acceptance milestone; it does not replace the full fifteen-family and learned-Core objective.

Management decisions for this plan:
- Keep one coordinator, one active product-code item and one bounded research question. Do not add agents, services or infrastructure merely to increase apparent activity.
- Complete or document the exact release blocker for an existing reviewed change before opening another overlapping implementation.
- Keep new paid services, model APIs, paid datasets, hardware purchases and trading capital at an authorized budget of USD 0. Existing subscriptions, electricity and owner time still have economic cost.
- Treat one month as a target for a serious research alpha, conditional on the first-week evidence. It is not a commitment to a fully trained, fifteen-family final system.
- Preserve source evidence, negative results and failed experiments. A valid NO_EDGE or DATA_INSUFFICIENT result is better than a fabricated winner.
- Keep broker connection, live activation, leverage/risk increases and commercial launch outside current authorization. Expansion is gated, not automatic.

This plan does not silently change immutable task definitions, repository protections or deployment configuration. Where existing documents still describe manual approvals or legacy workers, issue #42 must reconcile the actual behavior through reviewed changes. Routine owner authorization does not bypass platform permissions or required reviews. [R1, R6]

## 2. Evidence baseline and current gaps

Repository baseline inspected: main@16bcf1f1fe39d76eca510734a20d267ad651871d. The following is a dated snapshot, not a real-time dashboard. Recheck links before making a release decision.

| Area | Evidence-backed baseline | Gap before final evaluation |
| --- | --- | --- |
| Research components | Initial bars, execution, three experts, synthetic tournament, fundamental schema and import contracts exist | Initial implementation is not full product acceptance [R1-R4] |
| Execution corrections | PR #39 is open; its recorded review identifies successful CI and same-assistant review | Revalidate current candidate and resolve integration; no deployment inferred [R3] |
| Causality | #43 isolates dependence of entry decisions on future execution-data availability | Regression proof and reviewed correction [R4] |
| Real history | #37 records unresolved access/permission/coverage questions | Authorized sample and byte-derived coverage; no invented archive [R5] |
| Fifteen-family competition | #38 defines the intended league and Core handoff | Canonical registry, implementations, nested evaluation and measured selection [R7] |
| Research execution | #41 records local research requests reaching a disabled coding path | Verified research-capable execution or read-only handoff [R6] |
| Unattended delivery | #42 requires actual scheduled research and code/test receipts | Enabled schedules alone do not establish productivity [R6] |
| PC-independent Telegram | PR #29 remains a proposal with privacy and consumer-handoff concerns | Verified safe two-way delivery; not a prerequisite for offline product research [R8] |

Important unresolved distinctions: code exists versus acceptance passed; CI passed versus reviewed; merged versus deployed; report structure valid versus source verified; simulation result versus real-data evidence. Keep these distinctions visible in every status report.

The current plan has no verified ledger of actual account expenditure, no production availability commitment and no profitability evidence. Do not enter zeros for unknown spending or turn unknown capacity into an ETA.

## 3. Short-term delivery: first 30 days

Day 1 is the next recorded delivery kickoff after adoption of this plan. Record its UTC timestamp once; do not reset it on restart. The windows below are proposed calendar checkpoints. Dependencies and evidence determine promotion.

| Window | Primary outcome | Acceptance evidence | Decision at checkpoint |
| --- | --- | --- | --- |
| Days 1-3 | Finish a bounded correctness/release item | #39 release decision; #43 regression or precise blocker; real work receipt | Continue the ready code item, not another process rewrite |
| Days 4-7 | Prove the path from source to replay | Authorized sample or documented source blocker; integrity checks; representative runtime measurement | Confirm/revise the day-30 scope; do not pretend an unresolved source is ready |
| Days 8-14 | Deliver the three-expert real-data vertical slice | Same inputs reproduce proposals, decisions, costs, trades and manifest; relevant P1s resolved | Accept research-alpha foundation; not a performance claim |
| Days 15-21 | Establish the competition contract | Canonical fifteen-family register, bounded variants, data eligibility, split/search specification | Permit only eligible development-window experiments |
| Days 22-30 | Freeze and test a research-alpha candidate | Clean-environment replay, cost/risk report, known-limitations list and remaining milestones | Accept alpha, extend, or reduce the alpha scope explicitly |

Parallel research is allowed when independent of the current code item: source rights and point-in-time fields, then family definitions and selection design. Ranking cannot start merely because specification work can proceed.

The day-30 base target includes corrected replay, a verified data sample, auditable outputs, a fifteen-family specification and an initial comparison/selector where prerequisites permit. Full historical coverage, all news experts, full family selection and a trained neural Core are stretch outcomes, not assumed deliverables.

Week-one stop/replan rule: without an authorized sample/access decision, a measured representative run and a demonstrated delivery path, retain the goal but revise its date or explicitly narrow the alpha. Never relabel the narrowed alpha as the complete system.

## 4. Medium- and long-term roadmap

These are investment and sequencing horizons, not a promise that elapsed calendar time alone makes a release safe.

| Horizon | Deliverable | Promotion gate |
| --- | --- | --- |
| Days 31-60 | Expand eligible families; reproducible historical pipeline; nested within-family and cross-family selection | Verified data rights/coverage, fixed search budget, causal features, recorded trials and versioned replay |
| Days 61-90 | Compare deterministic, simple learned and small neural Core candidates | Temporal out-of-sample specialist predictions; matched costs/risk; frozen evaluation protocol; demonstrated incremental value or reject complexity |
| Months 3-6 | Shadow/paper readiness and operational hardening | No open release-blocking defects; rollback/restore drill; monitored data quality and model drift; separately authorized feed or demo access |
| Months 6-12 | Conditional extension to other instruments, horizons or a product offering | GBPJPY baseline remains reproducible; per-market cost/session validation; unit economics and legal/IP/data-rights review; explicit owner decision |

No automatic live milestone exists. A possible future small live pilot requires a separate written authorization defining broker, funding, loss limits, supervision, emergency stop and rollback. This handbook grants none of those permissions.

Growth sequence: first stabilize one instrument and one end-to-end workflow; then generalize instrument/session/cost contracts; only then introduce additional markets. Do not copy a GBPJPY threshold or cost model into another market without validation. Commercialization is an option to investigate, not the current funded scope or a revenue forecast.

## 5. First delivery queue and ownership

Use existing issues and their evidence; do not create duplicates of broad audit epics. Split the next necessary deliverable only when it needs its own acceptance boundary.

| Order | Work | Responsible function | Completion evidence |
| --- | --- | --- | --- |
| 1 | Revalidate and resolve PR #39 | Coordinator + developer/reviewer | Exact head/base CI, documented review and verified merge or exact blocking gate |
| 2 | Fix future-tail-dependent entry decisions, #43 | Kian development; Negar review function | Before-fail/after-pass regression; no changed historical entry when future data is removed |
| 3 | Resolve one source permission/access question, #37 | Saman data research | Claim-to-source matrix, contrary evidence, decision and next authorized sample step |
| 4 | Prevent unsupported local research dispatch, #41 | Integration development | Research cannot invoke legacy coding; actual report handoff test |
| 5 | Close next relevant correctness/provenance defect, #40 | Quant/data/development | Narrow acceptance tests and evidence; epic remains open for unresolved work |
| 6 | Reconcile family definitions and experiment design, #38 | Parsa + Niloofar specialties | Versioned registry and registered validation/search policy |

This ordering is dependency-aware: blocked release work does not prevent independent source research. A role label is not an assignment to an independently executing account. Record the actual executor and whether the run is interactive, scheduled, local or CI.

The owner owns objectives, funding, nonroutine permissions and future trading authorization. Arman owns selecting ready work and closing handoffs. Kian owns the implementation and test evidence. Negar owns a recorded review step; when the same assistant performs both, label SELF_REVIEW. CI supplies independent execution, not independent engineering judgment. Raha owns evidence-based reporting and freshness. Sohrab is reserved for genuinely required bootstrap actions. [R6]

Definition of Ready: concrete problem, expected behavior, allowed scope, input evidence, dependencies, test oracle, actual executor capability and next decision. An unsupported agent or inaccessible source is a blocker, not a task to launch repeatedly.

Definition of Done: acceptance evidence, current required CI, review attribution, applicable integration confirmation, updated documentation and no unresolved blocker in the item's scope. A parent epic closes only after all its own criteria pass. Local deployment requires its own receipt.

## 6. Research and fifteen-family competition

Retain the original S01-S15 identifiers from PROJECT_CONTRACT.md as the baseline until a reviewed taxonomy decision reconciles issue #38. Do not silently replace one list with another. The candidates are: EMA trend; Donchian breakout; volatility-compression breakout; session-range breakout; trend pullback; RSI mean reversion; Bollinger re-entry; failed breakout; multi-timeframe alignment; currency-basket strength; rate/yield context; UK macro surprise; Japan macro surprise; central-bank statement change; reversal after news shock. All begin UNTESTED. [R1, R7]

Every strategy card must specify family/variant/version, exact rule, sessions/timezone, horizon, entry readiness, exit/invalidation/expiry, source/license, required data and missing-data behavior. Record parameter bounds before testing. Filters and similar variants are not automatically independent strategies.

Separate three leagues: common-exit signal comparison; registered strategy-native systems under equal risk/cost assumptions; and the account-level Core comparison. The product contract's common signal league uses ATR14 stops, 3R targets and 240 real minutes. Do not call the current fixture defaults equivalent to that contract. Changes require an explicit design decision. [R1]

Selection process: tune bounded variants inside each training/development fold; select family representatives inside that fold; select the cross-family set using permitted development evidence; freeze it before the outer evaluation window. Train learned Core candidates from temporal out-of-sample specialist outputs. Final holdout is never used for choosing families, parameters, features or architectures.

Start with a modest registered search proposal, such as 2-4 variants per eligible family, and benchmark the actual workload before expansion. This is a planning ceiling to approve in the experiment specification, not a claim that 60 models have run or an excuse to exclude needed comparisons. Count all trials, including discarded attempts. Report cost stress, drawdown, turnover, uncertainty, co-loss/redundancy and incremental value; do not force a winner per family.

Research acceptance has three independent levels: STRUCTURE_PASS (contract fields valid), SOURCE_VERIFIED (claims checked against accessed sources, with contrary evidence), and EXPERIMENT_VALIDATED (a reproducible experiment supports the limited conclusion). A URL and a well-shaped report do not establish truth.

Macro/news eligibility requires first actual, forecast known before release, previous as-known, revisions, original publication and independently recorded observation/availability. Forex Factory is a secondary calendar cross-check; official releases and appropriately permitted forecast sources remain distinct. Daily vintages are not minute-level availability proof. No archive access means INELIGIBLE_DATA, not a zero forecast. [R1, R5]

The Core may select, decline or later combine a small nonredundant set under account risk controls. It is not a conversational LLM issuing live orders. Compare it with no-trade, a preselected specialist and a deterministic selector before adding complexity. Fly-inspired networks and reinforcement learning remain controlled later experiments, with matched baselines and no automatic promotion.

## 7. Engineering and scalability

Prefer a modular Python research application with clear interfaces over microservices. Keep provider ingestion, immutable data storage, causal features, strategy proposals, replay, selection, model evaluation and reporting separate. Development automation belongs outside the trading-decision path.

Record event time, available time, decision-ready time and executable fill time. Never fill retrospectively at an unavailable candle price. Keep bid/ask spread once, explicit commission/slippage/rollover assumptions, censoring and a single chronological account ledger. Before real ranking, specify P&L currency, conversion timing, quantity units, account equity, margin and risk sizing; GBPJPY price P&L must not be silently reported as USD account returns.

Storage target: immutable raw snapshots; versioned processed partitions; separate fixtures and protected holdout; manifests linked to bytes actually parsed. Store hashes, schema and evidence references in Git, not provider data whose redistribution is unapproved. An ignored file is not a backup. Never overwrite the only raw source when transforming data.

Optimize after profiling: parse once, cache causal feature arrays, avoid copying growing history prefixes and repeated full EMA rescans, and use bounded independent family/fold workers. Cache identity includes input checksum, transformation/code version, parameters and permitted cutoff. Any optimized path must match a trusted batch reference on adversarial fixtures before adoption.

Scale only when evidence requires it. Suggested review triggers: repeated memory exhaustion at the registered workload, unacceptable measured experiment duration, multiple contributors with conflicting writes, or a funded availability requirement. First reduce copies/search waste and add checkpoint/resume; do not silently buy compute. Expansion does not waive privacy or correctness.

## 8. Capacity, scheduling and progress measurement

Keep queue age, active work time and blocked time distinct. Preserve original deadlines and show revised estimates separately. Two consecutive actual runs with no output on the same item trigger a capability/dependency diagnosis; do not create another agent or rewrite the prompt again.

| Priority | Diagnosis/containment checkpoint | Small scoped verified-fix planning target |
| --- | --- | --- |
| P1 | 5 minutes after real work starts | 1 elapsed hour |
| P2 | 30 minutes after real work starts | 4 elapsed hours |
| P3 | 4 elapsed hours after real work starts | 24 elapsed hours |
| P4 | 24 elapsed hours after real work starts | 72 elapsed hours |

These retain the existing triage convention, not contractual SLAs. A scheduler that runs hourly cannot guarantee five-minute discovery. Large tasks require a concrete first deliverable and a separate whole-task estimate. Research blocked on source access does not become complete when a clock expires. [R4, W2, W3]

Each real delivery receipt contains UTC time, item, actor/mode, input and output SHA, action, actual tests/evidence, review attribution, merge/deployment state, blocker and next action. Do not infer that a scheduled run can write code because this interactive session can.

Review progress at the next actual run after a material change and at a weekly checkpoint when a run occurs. Keep one concise owner summary: delivered, currently working, blocked, next, cost/quota status. No additional daily meeting or reporting-only agent is required.

Measure verified deliverables, P1 closure/reopening, review/merge wait, data coverage, reproducibility, experiment runtime/memory and documentation freshness. Establish observed throughput over the first week before projecting an end date. Reserve roughly 20% of planned capacity for rework and verification as an initial planning assumption; replace it with measured rework data. Never convert model response time into assumed 24-hour engineering capacity.

## 9. Financial and resource plan

### 9.1 Approved envelope

Reporting currency is USD for service-budget comparison only; local cash costs keep their original currency and conversion date. Current authorized NEW service/API/data/hardware expenditure is USD 0; authorized trading capital is USD 0. These are caps, not verified actual expenditure. Actual invoices, remaining quotas, existing subscription allocations and local utility costs are UNKNOWN until reconciled. No access to private billing accounts is implied.

| Cost category | Current decision | Financial treatment |
| --- | --- | --- |
| Existing ChatGPT subscription | Use already available access only | Existing commitment; amount/allocation not supplied; no assumption of free API credit |
| New model API or cloud agent | Do not activate | New-spend cap USD 0 |
| VPS, paid hosting, larger runners | Do not provision | New-spend cap USD 0 |
| Existing computer | Use only within available capacity | Hardware sunk cost plus electricity/wear; uptime is conditional |
| GitHub standard public-repo CI | Use eligible existing workflow | Standard runner usage is free; storage, account quotas and larger-runner charges must be checked separately [W1] |
| Market/news/forecast data | Only verified permitted no-fee access | No paid feed or requester-pays path; availability is not assumed |
| Private mailbox/backups/storage | Prefer existing secure approved capacity | Check rights and quotas before use; no free-unlimited assumption |
| Live capital, legal/commercial launch | Not activated | No capital allocation or revenue plan approved |

Stop before creating any metered resource whose cost control is unknown. Budget alerts are not assumed to be hard spending stops. Verify applicable account controls before enabling usage; inability to verify them blocks activation. Review official pricing before any later proposal. The public repository is not permission to publish private data, and a private repository is not automatically unlimited free compute. [W1]

### 9.2 Cost model and controls

Incremental cash cost = new-service invoices + incremental power/network/storage + newly purchased equipment. Economic project cost = incremental cash + allocated existing subscriptions + owner/reviewer time valued at an explicitly chosen rate + hardware allocation. Track these separately; do not claim the whole project costs zero because new hosting costs zero.

Power estimate: kWh = measured average watts / 1000 x operating hours. Example assumption only: 120 W x 8 hours/day x 30 days = 28.8 kWh. Multiply by the actual local tariff; no tariff or electricity bill is asserted here.

Experiment estimate: required runs = eligible families x registered variants x temporal folds x stress cases, adjusted for caching and actual retries. Wall time depends on measured run time and safe concurrency. Forecast disk use from bytes per observation, actual coverage, compression and retained versions; reserve headroom before collection. Do not put a multi-year raw archive into GitHub Actions artifacts without a rights, capacity and billing review.

Maintain a private financial ledger with date, supplier/category, committed amount, actual invoice, currency, exchange-rate source/date when needed, quota usage, approver and evidence. The public handbook stores only the approved envelope and sanitized totals. First-week financial action: inventory existing entitlements and measure one representative job, without adding services. Weekly: reconcile actuals and quota forecasts. Monthly: continue/replan/stop decision against delivered evidence, not sunk cost.

### 9.3 Funding and business scenarios

A: current zero-new-service research mode. Accept intermittent compute, bounded experiments and possible source limitations; do not promise continuous service.

B: future reliability upgrade. Consider only after an observed bottleneck and owner funding approval. Prepare a current supplier quote, monthly hard cap, one-time migration cost, security implications and exit plan. Amount remains TBD/NOT_APPROVED; no service is purchased by this plan.

C: future product/commercial investigation. Only after reproducible research: choose an intended customer/problem, rights to distribute outputs, jurisdictions, support obligations and realistic unit costs. Keep validation interviews separate from selling investment claims. No customers, revenue or profit forecast is assumed.

Possible break-even analysis, only with real prices: paying customers needed = fixed monthly operating cost / (net revenue per customer - variable service/support cost), rounded up. If contribution margin is nonpositive, no finite break-even follows. Trading returns are uncertain and are not the project's funding source in this plan.

## 10. Risk, privacy, legal and continuity register

| Risk | Trigger / evidence | Owner function and response |
| --- | --- | --- |
| Invalid research outcomes | Future-data dependence or accounting mismatch | Quant/QA: contain affected ranking, regression and re-evaluation; #40/#43 |
| Data access/rights gap | Source terms or archive coverage unresolved | Saman: clarify permitted path or alternative; do not scrape/publish by assumption; #37 |
| Cosmetic research approval | Structural PASS treated as factual approval | Research/QA: source evidence level and actual source review; #41/#42 |
| Unattended execution unproved | Run recorded without deliverable | Arman: real scheduled receipts, capability diagnosis; #42 |
| Private Telegram text exposed | Public mailbox or untrusted state marker | Security/operations: keep #29 draft, authenticate state and isolate private content |
| False diversified winners | Correlated variants/full-history selection | Parsa: nested selection and redundancy/cost analysis; #38 |
| Resource or quota exhaustion | Memory/disk/runner limit approached | Engineering/finance: bounded workloads, checkpoint and stop before paid overage |
| Key-person/assistant dependency | Session/context loss or local machine off | Coordinator: repository receipts, versioned handoffs, verified restore and alternate authorized execution |
| Stale documentation | Evidence changed without source revision | Custodian: update affected section/status; mark stale rather than reconstruct history |
| Commercial/legal uncertainty | Plans to sell, distribute data or trade for others | Owner: determine jurisdiction, IP/data licenses and qualified legal/accounting review before launch |

No jurisdiction is inferred from an estimated user location. This is a compliance work register, not a legal determination. Do not silently add an open-source license, publish licensed data or assume public source availability grants unrestricted commercial use.

Security baseline: least privilege, secret storage outside code/reports, no private messages in public issues by default, and no untrusted pull-request code executing with broker or bot credentials. Authenticated author/app identity matters; a marker string is not authority.

Backup/restore proposal: preserve immutable source and model manifests, take state snapshots at accepted checkpoints, keep an approved separate copy, and verify restore before releasing an operational build. A second folder on the same disk is not an independent backup. If no safe second storage exists under the budget, record continuity as blocked instead of claiming disaster recovery. Desired recovery point is the last accepted checkpoint; recovery time is measured by the first drill, not invented now.

## 11. Acceptance and the final-test contract

Distinguish acceptance of the software from evidence of a trading edge. A technically correct run may conclude that no candidate beats its baselines. Do not change success thresholds after seeing final holdout results.

Before final evaluation, freeze code/environment, dataset checksums and permission scope, all candidate/model versions, parameters, cost and account conventions, selection policy, metrics, exclusion rules, uncertainty method and stop conditions. Document every earlier look at the proposed holdout. A period that influenced design is no longer untouched. [R1]

Technical release gates:
- No unresolved P1 in the evaluated path; current tests and review meet repository rules.
- Feature, forecast and entry timing is causal; missing future observations cannot rewrite a prior decision.
- Data manifests are tied to parsed bytes; fixtures and evaluation data cannot mix.
- One execution/account contract is used for comparison; currency, costs, overlap, censoring and risk are explicit.
- A clean-environment replay produces identical decision/trade records and numerically equivalent outputs within a predeclared tolerance.
- Model selection and transforms use only permitted development information; final evaluation cannot retune them.
- Output includes rejected candidates, data limitations, failed tests and an evidence-backed PASS/FAIL/INCONCLUSIVE verdict.

The final evaluation package contains a release manifest, one documented entry point, frozen experiment specification, detailed audit records, baseline comparisons, uncertainty/cost stress, resource measurements, known risks and a plain-language owner report. The one-command entry point is a deliverable to implement; this document does not pretend it already exists.

Run final evaluation only after this checklist passes. Shadow/paper acceptance adds actual uptime/freshness, restart/checkpoint, stop/rollback and credential-separation tests. Live approval remains a separate owner decision even if paper results are favorable.

## 12. Operations and truthful reporting

Product research must continue independently of Telegram delivery where safe. Telegram is a control/reporting interface, not the authority for source truth or a prerequisite for every offline computation. Local and cloud consumers must not poll the same bot concurrently without a verified handoff. No generic repair should delete webhooks or reset offsets without understanding the active consumer.

Return cached status with its source revision, observation time, last successful delivery and explicit stale/blocked state. Local deployed revision and GitHub main revision are separate fields. A merge must never be described as a local installation without deployment evidence. Keep private conversations separate from public project receipts. [R6, R8]

Scheduled tasks and GitHub workflows have permission, availability and scheduling limitations. GitHub schedules can be delayed or dropped; ChatGPT tasks can require additional action. The current project has no demonstrated continuous 24/7 coding or instant Telegram service. Do not promise a selected chat model is guaranteed for scheduled runs. [W2, W3]

Incident response: preserve evidence, contain the unsafe action, identify the last good revision/checkpoint, make a scoped correction, verify it and record recurrence prevention. Respect owner pause/stop; a watchdog must not undo an intentional stop or bypass a permission block. Notify on material changes and unresolved deadline misses, not repeating unchanged heartbeats.

## 13. Living documentation and change control

Canonical reading path: repository README -> this handbook -> linked evidence/contracts. PROJECT_STATUS.json is a dated, non-executable snapshot for concise status; it does not schedule work, grant authority or replace the runtime database. The Persian companion and exported Word document are human-readable views of this version. Exports are snapshots; GitHub history is the versioned record.

Custodian: Arman function. The person/agent making a substantive change proposes the matching documentation update; the reviewer checks it. Update affected acceptance, interface, assumption, cost, risk and operating sections in the same PR, or link a bounded follow-up that blocks release when the omission is safety-critical. A typo-only change can declare 'documentation impact: none' with a reason.

After an actual merge, source-validation result or deployment, update only the changed status fields with evidence. Do not rewrite the handbook on every heartbeat. At the next actual weekly review, roll up delivered work, remaining gates, financial/quota status and forecast changes. More than seven days without verifying the overview means REVIEW_REQUIRED, not automatically healthy. Historical evidence remains historically valid at its recorded revision.

Versioning: patch for factual/status corrections; minor for reviewed compatible additions; major for scope, architecture, execution or acceptance changes requiring a decision. Record old/new assumptions and consequences. Existing tests, task immutability, data rights and authorization gates are not overridden by editing this document.

Initial decision register:
- D01: first milestone is a small real-data three-expert replay, not a falsely complete fifteen-family system.
- D02: retain original S01-S15 identifiers pending a reviewed reconciliation with #38.
- D03: no new paid services or trading capital; account actuals remain unknown until reconciled.
- D04: one active product change and one bounded research question; no new agent by default.
- D05: self-review is labelled; unattended work requires actual scheduled receipts.
- D06: current main, proposed fixes and local deployment have distinct status.
- D07: this handbook is a management baseline; policy/runtime reconciliation remains work under #42.

Change request template: problem; evidence; proposed change; affected interfaces/data/cost/risk; options including doing nothing; decision owner; acceptance and rollback; actual implementation reference. Run receipt template: time; item; actor/mode; source SHA; action/output; actual tests; review; merge/deployment; blocker; next step.

Changelog 1.0: established short/long horizons, financial envelope, evidence gates, risk register, ownership and document-maintenance rules. Documentation delivery does not close #42 or prove any code, research pipeline or deployment complete.

## 14. Source register

Repository evidence is recorded at the inspected revision or linked item. External service references were checked for planning on 22 September 2026 and must be rechecked before a financial or operational activation. No source is evidence of this project's profitability.

[R1] Product contract, baseline revision: https://github.com/mojtabashariatzade/trading-agent-lab/blob/16bcf1f1fe39d76eca510734a20d267ad651871d/docs/PROJECT_CONTRACT.md

[R2] Task definitions, same baseline: https://github.com/mojtabashariatzade/trading-agent-lab/blob/16bcf1f1fe39d76eca510734a20d267ad651871d/planning/tasks.json

[R3] Execution audit PR and review evidence: https://github.com/mojtabashariatzade/trading-agent-lab/pull/39

[R4] Remaining integrity work and scoped causality defect: https://github.com/mojtabashariatzade/trading-agent-lab/issues/40 and https://github.com/mojtabashariatzade/trading-agent-lab/issues/43

[R5] Data-access investigation: https://github.com/mojtabashariatzade/trading-agent-lab/issues/37

[R6] Research-routing and delivery-management findings: https://github.com/mojtabashariatzade/trading-agent-lab/issues/41 and https://github.com/mojtabashariatzade/trading-agent-lab/issues/42

[R7] Fifteen-family competition scope: https://github.com/mojtabashariatzade/trading-agent-lab/issues/38

[R8] Proposed PC-independent Telegram relay: https://github.com/mojtabashariatzade/trading-agent-lab/pull/29

[W1] GitHub Actions billing: https://docs.github.com/en/billing/concepts/product-billing/github-actions

[W2] GitHub workflow scheduling limits: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

[W3] OpenAI scheduled tasks and permissions: https://help.openai.com/en/articles/10291617-tasks-in-chatgpt
