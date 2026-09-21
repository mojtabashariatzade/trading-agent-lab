# Market Grammar and autonomous trading architecture

Design version 0.1 | 22 September 2026 | Status: PROPOSED_RESEARCH_DESIGN

Reviewed repository baseline: 72dd7dfe7fcf98e2d12d87e39e4686f2e21277e9. This document incorporates the owner-supplied Market Grammar proposal and the correction that income must come from the system's own LONG/SHORT trades. It adds no trading adapter, learned model or executable course rule. The supplied proposal is not the raw course dataset and does not prove the teacher's claims or the number of videos actually reviewed.

## 1. Product direction and source framing

The final product is an autonomous trader: observe, decide, size, execute, manage and exit positions, with deterministic risk control and reconciled P&L. Its reports are operational evidence, not a product to sell. Current development remains research/replay; later paper and live activation require their respective gates.

The supplied hypothesis is Universal Market Grammar / Universal Market Dynamics Core, not a proven universal law. It asks whether normalized representations of levels, swings, structure, liquidity events, compression, expansion, breakout, retest, rejection and regime transitions can transfer to previously unseen instruments.

The course is an Expert Knowledge Layer, not a giant hard-coded strategy. Its proposed decision vocabulary is location + structure + liquidity + timing + breakout/retest + candle confirmation + supporting evidence + risk. The proposal explicitly says an EMA cross alone is not an entry rule and reported counts such as 5-6 or 8-9 confluences are TEACHER_CLAIM, not thresholds to enforce.

The source requests immutable video -> timestamp -> transcript -> frame -> concept provenance; retention of unknown/conflicting rules; separate teacher reconstruction and trading-validity evaluation; retention of the classic fifteen-family league and macro/news layer; and no current broker/live activation. The decisions below preserve those constraints. Implementation refinements in sections 4-8 are engineering proposals, not statements that the source or repository already implements them.

## 2. Conflicts found in the inspected repository

| Current artifact | Conflict or gap | Scoped decision |
| --- | --- | --- |
| Handbook v1.1, revenue plan, #45 and R07 | Optional software/customer revenue is outside the owner's objective | Remove the route and reassign its work to trading research; retain audit history only |
| docs/PROJECT_CONTRACT.md objective | GBPJPY/M15 can be read as a fixed product boundary | Keep it as the first benchmark; version instrument/session/currency interfaces before later expansion |
| trading_lab/contracts.py and tournament/core.py | Seed BUY/SELL/PASS selection and fixture replay are not a complete execution/position loop | Design LONG/SHORT intents separately from orders, positions and mode-specific execution; do not relabel existing seeds as deployed trading |
| tournament/core.py | SYNTHETIC_TEST_ONLY and future m1_bars entry dependency | Keep real rankings disabled; #40/#43 remain prerequisites |
| Existing feature and specialist interfaces | No implemented Geometry -> State -> Confluence layer established by this review | Define an optional interface boundary first; do not replace existing experts |
| Entry-focused proposal contracts | No complete staged management, partial-fill or live reconciliation contract | Register management as part of each strategy and test the lifecycle before operational use |
| agentops/research.py structural gate | Report structure is not source truth or an empirical result | Distinguish structural, source and empirical verification; reuse #41/#42 |
| Contract family list versus #38 | The two proposed taxonomies differ | Preserve S01-S15 pending explicit mapping; no silent replacement |
| Course evidence availability | Raw videos/transcripts/frames are not the two supplied proposal files | Schema and ingestion plan only; no claim of importing or reviewing the course in this change |

AGENTS.md, the product contract, handbook/status, delivery plan, current seed decision/tournament code, #38/#40 and open PR state were inspected for this scoped comparison. This is not a claim that every file or the user's Windows runtime was audited.

## 3. Target boundaries

Proposed flow:

    Permitted raw market observations
      -> Market Geometry Core (causal events and normalized movement)
      -> Market State Representation
      -> Course Expert Layer / Classic Specialists / Session-Liquidity Context
         / Macro-News-Rates / Cross-market Context
      -> Structured Confluence Engine
      -> Trading Decision Core: LONG | SHORT | PASS | WAIT | DATA_INSUFFICIENT
      -> Deterministic risk veto and position-size validation
      -> Mode-specific execution + position management + account reconciliation
      -> Persisted trade/equity evidence and operational feedback

The Development Core schedules software/research work; it does not acquire trading authority. Instrument identity may be withheld from a representation experiment, but the execution and risk layers must know the instrument, contract size, currency, session and permitted venue. Model uncertainty never disables those controls.

This diagram is a design, not new runtime code. Existing BUY/SELL/PASS enums remain unchanged until a reviewed adapter defines how directional intents, order sides and position effects map to one another.

## 4. Causal geometry and structured confluence

A geometry observation should carry instrument, event interval, detection/confirmation time, available_at, lookback/cutoff, algorithm/version and evidence reference. Swings and break-of-structure must be usable only when confirmed; a pivot drawn retrospectively on an earlier candle cannot be consumed earlier than its confirmation. Appending future data must not rewrite past decisions.

Causal normalization is fitted or updated only on allowed past observations. Candidate examples include normalized returns, distances to levels in past-volatility units and range location. Do not set numerical tolerances, swing spans, psychological-level spacing or Fibonacci anchor rules from incomplete course descriptions. Register each chosen definition as a hypothesis with an explicit alternative and test.

Classify proposed inputs as HARD_GATE, SOFT_EVIDENCE, CONTEXT or MANAGEMENT and record their source/dependency groups. Determine redundancy before combining them; several EMA-derived features do not provide several independent confirmations. Do not invent a weighted score. Any learned weighting, thresholds, regime detector or calibration belongs inside temporal development folds.

PASS means no justified entry; WAIT means await a defined condition with expiry; DATA_INSUFFICIENT means the required information is missing. None forces a BUY or SELL. An open position remains under its registered management/risk policy even when the entry model passes.

## 5. Course evidence ingestion and schema proposal

Keep raw video, corrected transcripts and extracted frames immutable and in approved private storage. Do not upload course media or full transcripts into the public repository. Git contains schema versions, permitted summaries and nonsecret evidence identifiers only. Preserve corrections as new versions; do not overwrite the original or silently resolve contradictions.

Proposed observation fields:

| Group | Fields |
| --- | --- |
| Identity/provenance | observation_id, video_id, video_time_start/end, transcript_reference/version, frame_reference/hash, extraction_version, annotator/mode, annotation_created_at |
| Interpretation | concept, setup_stage, market_state, level_type, structure_state, liquidity_event, session, confirmation, confluences |
| Trade logic | invalidation, stop_logic, target_logic, management_action, entry/exit timing, explicit no_trade_reason |
| Source uncertainty | quoted_teacher_confidence, ambiguity, contradiction_id, missing_fields, evidence_status |
| Research status | claim_stage, formalization_version, proposed_test, experiment_reference, validation_domain/cutoff |

`evidence_status` preserves UNKNOWN / CONFLICTING separately from `claim_stage`: TEACHER_CLAIM -> FORMALIZED_HYPOTHESIS -> EMPIRICALLY_VERIFIED. VERIFIED always has a stated domain, tested version and evidence; it never means proven for all markets. Teacher confidence is source metadata, not a calibrated trading probability.

Unknowns retained from the proposal: retest tolerance, strong-move definition, psychological-level generation, swing anchors for Fibonacci, session interpretation, mandatory/optional confluences, sizing, daily loss limits, maximum trades and complete money-management rules. Missing is not zero or false.

Ingestion steps: inventory actually available evidence; hash and version it; extract observations with links; check reference integrity; review ambiguous/conflicting cases without forced consensus; then propose formalized hypotheses. Continue dense visual/transcript review under the separate course-extraction workflow. Do not start speech recognition when an accepted corrected transcript already exists. This change performs none of those raw-media ingestion steps.

## 6. Teacher reconstruction is not market validity

First evaluate whether annotations/model reconstruction accurately represent what the teacher said: concept and no-trade labels, event sequence, location/management actions and inter-annotator disagreement. Hold out entire lessons/examples rather than near-duplicate neighboring frames. Record ambiguity rather than guessing a numerical answer.

Separately test predictive and trading value with causal market data, realistic common execution, risk limits and unseen periods. Course screenshots can show future candles or hindsight-selected examples; record the decision cutoff, mask later information for reconstruction tasks and do not treat their apparent winners as unbiased performance samples.

A model can reconstruct the lesson well and still fail trading validation. A poorly supported lesson cannot become a trading rule merely because it has a citation or matches the teacher.

## 7. Four-way comparison and cross-instrument protocol

Retain four research candidates:
A. Classic Specialists: the existing fifteen-family program.
B. Course Knowledge Model: formalized structure/liquidity/session/management hypotheses.
C. Universal Market Dynamics: learned normalized market-behavior representation.
D. Combined: eligible A/B/C outputs with macro/news context and the Decision Core.

Use ablations to measure each contribution. Preserve signal/common-exit, native-system and Core/account leagues; course management belongs to the native-system definition. Match data availability, costs, risk, search budget and evaluation opportunities. Never preselect C or D as the winner. No sufficient edge is an acceptable result.

Proposed leave-one-instrument-out protocol:
1. Register eligible instruments and licensed data coverage before results. The proposal's EURUSD, GBPUSD, USDJPY, AUDUSD, GBPJPY and XAUUSD are examples, not an available dataset claim.
2. Reserve an entire instrument for outer evaluation, and rotate the held-out instrument in prespecified experiments. A calendar-time outer holdout is also needed; training on later dates from other instruments must not leak future macro regimes into earlier tests.
3. Tune features, normalizers, variants, family selection, representation and Core only inside permitted development instruments/time folds. Preserve the final untouched evaluation separately.
4. In the strict zero-shot experiment, no held-out labels or fitted statistics are used. Any rolling normalization using its causally available past must be predeclared. Report a separate adaptation experiment if target-history fitting is allowed.
5. Test raw price-scale and symbol-identity leakage; compare symbol-aware and masked controls. Volatility/session behavior can still reveal identity, so removing the symbol string is not proof of invariance.
6. Separate cross-market context known at prediction time from held-out labels. Do not sneak the held-out instrument's future returns into training via a currency basket or correlated target.
7. Report instrument-by-instrument net outcomes, drawdown, costs, abstention, uncertainty and failure cases; do not let pooled results hide a failed market. Show transfer degradation relative to the in-domain baseline.

GBPJPY/M15 remains the first working benchmark. Designing an instrument field now is reasonable; collecting many markets or training a universal model now is not part of this correction.

## 8. Position lifecycle and risk are part of the trading product

Register entry, invalidation, protective exit, staged targets, time expiry and breakeven logic together with each candidate. Unknown management rules remain unresolved research. An independent risk layer may veto entries or apply separately specified emergency actions; it does not invent teacher parameters.

Before operational use, tests must cover long and short entry/exit symmetry, sizing and currency conversion, protective-order behavior, rejected/partial/duplicate fills, disconnect/restart reconciliation, stale quotes, margin/cash, daily loss constraints and correlated exposure. Pending orders and open positions must survive process restarts without duplicate exposure. Net trading income is derived from reconciled account events, not the number of generated signals.

Current requests authorize this design alignment, not live execution. Broker activation remains a separately authorized deployment step after validated replay, unseen evaluation and shadow/paper gates.

## 9. Staged roadmap and reuse of existing work

| Phase | Outcome | Gate / existing work |
| --- | --- | --- |
| 0 | Course evidence extraction continues independently | Provenance and unresolved claims retained; no premature executable rules |
| 1 | Fix research-integrity P1s | #40, #43, #46 and relevant #39 corrections before real rankings |
| 2 | Formalize Market Grammar ontology | Reuse R07 / #38; schema design and causal definitions, not learned performance |
| 3 | Reconstruct course logic from annotations | Available reviewed evidence; teacher-reconstruction metrics |
| 4 | Test course-derived rules empirically | Valid data and registered temporal validation |
| 5 | Build a Universal Market Dynamics prototype | Bounded model/search proposal after representation baselines |
| 6 | Leave-one-market-out generalization | Prespecified instruments, dual market/time isolation and per-market reports |
| 7 | Compare A / B / C / D | Equal execution and risk, ablation, uncertainty and no forced winner |
| 8 | Train/evaluate Decision Core | Temporal out-of-sample expert outputs; PASS/WAIT/data gates |
| 9 | Portfolio/multi-market layer | Aggregate exposure/correlation/currency and instrument-specific costs |
| 10 | Shadow/paper operational validation | Separate execution, monitoring and recovery acceptance |

Later authorized live use is the final product deployment objective, not an action performed by this phase table. The proposal does not justify pushing all new experiments into the existing 30-day alpha deadline.

Reuse #38 for representation/competition design, #40 for integrity, #41/#42 for research and delivery evidence, and #45 for net trading P&L. R07 replaces the removed sales slot with this bounded design work; R08 focuses on position-management acceptance. No new issue or speculative worker is needed merely to record these changes.

## 10. Delivery status and source trace

Source basis: the two owner-supplied Market Grammar proposal attachments, both fully available as text in this conversation. Their course observations remain source claims; no independent video review is claimed. This document preserves their terminology and adds explicitly labelled engineering design decisions.

Implemented by this change: documentation and planned-work scope corrections only. Proposed only: Geometry Core, state representation, confluence contracts, course ingestion, learned representation, four-way experiments, leave-one-instrument-out evaluation and operational position adapter. No product code, training, real data collection, broker activation or local deployment is performed.

Repository references at the inspected baseline: AGENTS.md; docs/PROJECT_CONTRACT.md; docs/PROJECT_HANDBOOK.md; docs/PROJECT_STATUS.json; planning/delivery_plan.json; trading_lab/contracts.py; trading_lab/tournament/core.py; issues #38/#40/#45. Keep the integrity work first. Review the next implementation as a small separately tested change, not a broad replacement of the current system.
