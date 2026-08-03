# AI Trading Copilot — Frozen Small-Capital LIVE Roadmap

## Scope freeze

This roadmap contains exactly eight prerequisite tasks. No ninth prerequisite
task may be introduced. New work is either implementation within one of these
eight tasks, a defect fix within the active task, or an optional post-launch
improvement. A requirement discovered later belongs to the closest existing
task rather than a new roadmap phase. Profit is never guaranteed.

LIVE means automated real-money order placement and management in the connected
brokerage account after all safety gates pass. LIVE remains disabled by default.
The launch scope is NIFTY/NSE/NFO and SENSEX/BSE/BFO only.

## Final product definition

The finished copilot continuously analyses NIFTY and SENSEX: price and market
structure; candlestick/chart patterns; trend/momentum; volume; volatility;
multi-timeframe alignment; option chain; OI/OI change/PCR; support/resistance/
max pain; Greeks/premium behaviour; market regime; broader/external context;
and data quality, freshness, and contradictions. It compares both markets and
selects the strongest eligible risk-adjusted opportunity while explaining the
winner and loser.

It reads user capital and calculates an affordable contract, lots/quantity,
capital required, maximum permitted loss, entry, stop-loss, T1/T2/T3. It
returns CALL, PUT, WAIT, NO_TRADE, HOLD, or EXIT; monitors open trades to
closure; announces targets; moves/protects stops only when policy permits;
warns about confidence deterioration; recommends unsafe early exit; maintains
PAPER and LIVE journals; and produces daily, weekly, and monthly reports with
identical reporting semantics. It never claims guaranteed profit.

## The eight final tasks

### 1. Authoritative live evidence

Purpose: establish truthful, timestamped, typed NIFTY/SENSEX and option-market
evidence. Foundations: `certified_live_provider_readers`, Angel normalization,
P5 contracts, certified shared India VIX, and typed optional external context.
Institutional/global/event evidence and breadth remain optional under the
current policy: the shared external projections are wired into each child’s
canonical market-regime result, but missing optional evidence does not
independently block a candidate. No unapproved provider is introduced, and
unavailable context and the actual terminal component are attributed truthfully
rather than fabricated. Future approved adapters remain optional improvements
and do not reopen Task 1. Exit gate: every required active input is
provider-proven or explicitly unavailable.
Depends on: none. Excludes: decision, planning, orders, and LIVE execution.

### 2. Fourteen-pillar decision certification

Purpose: certify complete per-market evidence and deterministic two-market
selection. Foundations: typed technical, multi-timeframe, option-chain,
regime, broader-market, candidate, parent-cycle, and Task 8 canary contracts.
Remaining work: close unproven pillars and certify contradiction/freshness and
winner/loser rationale. Exit gate: exactly-once NIFTY/SENSEX parent cycles with
all required pillars or explicit unavailable evidence. Depends on: Task 1.
Excludes: capital allocation and lifecycle execution.

Task 2A exposes one immutable typed contribution record per canonical pillar.
Grouped-source provenance is explicit: it does not fabricate independent
directions or scores when the active adapters expose only grouped evidence.
This changes neither confidence, score, eligibility, nor action; Task 2B will
consume these records for final-confidence certification.

Task 2B adds a deterministic PAPER shadow confidence ledger. It exposes every
counted and excluded source, and retains quality, contradiction and suitability
hard-block effects without double counting aggregates. Legacy candidate
confidence and score remain authoritative; neither selection nor parent ranking
changes until equivalence and policy approval support a later Task 2C step.

Task 2C adds PAPER-only child CALL, PUT, WAIT, and UNAVAILABLE projections.
WAIT is a valid non-entry decision, while parent NO_TRADE remains parent-owned.
CALL and PUT do not imply affordability, contract planning, or execution; HOLD
and EXIT remain Task 4 lifecycle actions. Parent ranking and the shadow ledger
remain unchanged; Task 2D will add evidence-grounded winner/loser explanations.

Task 2D adds deterministic typed child and parent explanation projections from
canonical evidence only. Grouped pillar limitations remain explicit; WAIT and
UNAVAILABLE remain distinct. No generative model is canonical reasoning, and
explanations do not change confidence, eligibility, action, or ranking. Task
2E will provide the final end-to-end certification matrix.

Task 2E1 adds a typed parent winner/loser/NO_TRADE explanation validated
against existing parent ranking and child outputs. It adds neither scenario
fixtures nor a CLI; Task 2E2 will add the typed certification result and
composer, and Task 2E3 the deterministic scenario matrix and provider-free CLI.

Task 2E1.5 certifies parent-cycle identity propagation: the cycle originates
solely at `TwoMarketParentCycleInputV1.parent_cycle_id` and is shared unchanged
by NIFTY and SENSEX. Candidate and observation IDs remain market-specific, and
there is no certified candidate-ID fallback. Scoring, actions, explanations,
and ranking remain unchanged; Task 2E2 is unblocked, but Task 2 is not complete.

Task 2E2 adds immutable certification-result and fixed-fixture contracts with
a provider-free single-result composer/report foundation. Both markets retain
the truthful shared parent cycle; Task 2E3 remains responsible for the full
scenario matrix, aggregate report, CLI, and final Task 2 gate.

### 3. Capital, option selection and risk planning

Purpose: plan only the selected eligible market using actual capital and option
constraints. Foundations: P6 input/result contracts, option contract ranking/
selection, risk policy/pipeline, entry/stop/three-target evaluators, and
selected-market planning bridge. Remaining work: certified two-market selected
handoff and evidence completeness in the active composition. Exit gate: a
selected-market-only PAPER plan proves affordability, lot/quantity, costs,
maximum loss, entry, stop, T1/T2/T3, or deterministic NO_TRADE. Depends on: 2.
Excludes: fills, monitoring, broker submission.

### 4. PAPER trade lifecycle

Purpose: persist and monitor PAPER positions from entry through reconciliation.
Foundations: P7/P8 contracts, entry/position evaluators, target/stop/terminal
appliers, JSON repositories, recovery services, portfolio persistence, and
monitoring executors. Remaining work: active-position discovery and recovery
wiring in the certified runtime. Exit gate: idempotent PAPER entry, monitoring,
HOLD/risk/target/exit, EOD closure, restart recovery, and reconciliation.
Depends on: 3. Excludes: real broker order methods.

### 5. Prediction verification, journals and reports

Purpose: preserve predictions and later outcomes, then reconcile reports.
Foundations: orchestration journal, audit events, paper-trade persistence,
session manifests/analytics, runtime summaries, research reports, and dashboard
publication. Remaining work: immutable recommendation/outcome linkage,
standardized outcome mapping, PAPER/LIVE journal distinction, and reconciled
daily/weekly/monthly reports. Exit gate: persisted prediction-to-outcome records
and restart-safe reconciled reports. Depends on: 3 and 4. Excludes: count
inflation from replay or dashboard refresh.

### 6. Automated 100 NIFTY + 100 SENSEX real-time PAPER certification

Purpose: one continuous supervised real-market PAPER certification session.
Foundations: Task 8 canary, journals, lifecycle, publication, and reports.
Every defect, fix, retest, prediction-marking issue, monitoring issue, journal
issue, dashboard issue, and report issue discovered during this session remains
inside Task 6 until its exit gate passes. Exit gate: the rules in
`TASK6_REALTIME_PAPER_CERTIFICATION_RULES.md`. Depends on: 1–5. Excludes:
replay/historical counts and LIVE orders.

### 7. LIVE execution and safety layer

Purpose: create a separately reviewed real-order boundary after PAPER proof.
Foundations: repository PAPER guards, safety validators, broker abstraction,
emergency halt, and operator controls. Remaining work: explicit LIVE authority,
order lifecycle/reconciliation, kill-switch/adverse-path certification, and
operator confirmation. Exit gate: reviewed, fail-closed LIVE safety evidence.
Depends on: 6. Excludes: enabling LIVE by default or dashboard authority.

### 8. Supervised small-capital LIVE launch

Purpose: operator-supervised, small-capital rollout after Task 7 acceptance.
Foundations: all prior gates. Remaining work: launch runbook, monitored pilot,
rollback/reconciliation, and post-launch review. Exit gate: accepted supervised
pilot with no unresolved critical safety incident. Depends on: 7. Excludes:
profit promises and autonomous scaling.
