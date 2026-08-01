# Two-Market Certified PAPER Runtime Status

## Scope and audit method

This is a static repository audit of the certified automated PAPER runtime for
the NIFTY/NSE and SENSEX/BSE scope. No tests were run and no production runtime
behavior was changed. “Current runtime” means the composition built by
`build_certified_launcher()` / `build_automated_paper_launcher()`.

## Current behavior

**Classification: single-market configured evaluation, with no cross-market
comparison.** It is neither true two-market parallel evaluation nor sequential
two-market evaluation.

`CertifiedRuntimeCompositionSettingsV1` has one `primary_symbol` and one
`primary_exchange` (default `NIFTY`/`NSE`). `CertifiedCycleSource.__call__()`
resolves that one identity, reads one quote, validates one session, and returns
one `PaperOrchestrationCycleInputV1`. The outer runtime invokes one opportunity
input factory and one monitoring input factory per scheduled cycle; it has no
batch loop, executor pool, or fan-out over the two certified instruments.

Consequently, the `CertifiedPaperRuntimeSafetyConfigV1(instruments=("NIFTY",
"SENSEX"))` declaration is an allowlist/safety declaration, not an execution
schedule. A caller may configure SENSEX as the primary market, but that replaces
NIFTY for the launcher instance; it does not add SENSEX to the same cycle.

### Per-cycle requirement status

| Requirement | Current status | Evidence |
| --- | --- | --- |
| Evaluates NIFTY | Only when NIFTY is the configured primary; default yes | `services/paper_orchestration/certified_runtime_composition.py:219-220, 548-557` |
| Evaluates SENSEX | Only when SENSEX is the configured primary; default no | `services/paper_orchestration/certified_runtime_composition.py:219-220, 548-557` |
| Evaluates each market exactly once | No two-market batch exists | `services/paper_orchestration/certified_runtime_composition.py:530-646` |
| Ranks both markets | No | `services/paper_orchestration/certified_live_provider_readers.py:375-514` |
| Selects strongest eligible market | No cross-market selection | `services/paper_orchestration/certified_live_provider_readers.py:424-495` |
| Preserves why rejected market lost | No rejected peer exists in a certified cycle | `services/paper_orchestration/certified_live_provider_readers.py:497-513` |

## NIFTY path

1. The default settings select `NIFTY`/`NSE`.
2. `market_spec_for()` resolves the fixed NIFTY spot token and `NFO` option
   exchange.
3. The cycle source gets one live quote and builds a timestamped certified
   observation and session validation.
4. The data authority reuses that quote; the analysis reader fetches
   multi-timeframe candles for the same exchange/token; the opportunity reader
   invokes `LiveOptionDecisionPipeline` for NIFTY/NFO.
5. A READY result can continue through the P6 input factory, P8 admission, P7
   entry, and P8 activation only in explicit automated-PAPER mode.

Relevant sources: `services/paper_orchestration/certified_runtime_composition.py:499-646`,
`services/paper_orchestration/certified_live_provider_readers.py:250-514`,
`services/market/live_multi_timeframe_data.py:92-212`, and
`services/live_option_decision_pipeline.py:801-891, 1375-1558`.

## SENSEX path

The provider path is implemented but is not scheduled concurrently with NIFTY.
`market_spec_for("SENSEX", "BSE")` resolves the BSE spot token and the BFO
option exchange. If settings make SENSEX primary, the exact same single-market
cycle machinery passes BSE, the SENSEX token, and BFO to the candle and option
pipeline.

The certified market-spec allowlist is deliberately exact: NIFTY/NSE/token/NFO
and SENSEX/BSE/token/BFO are the only accepted tuples. The general underlying
registry likewise contains precisely these two underlyings, although the broader
canonical identity registry and four-market ranking contracts also include
BANKNIFTY and FINNIFTY. This scope mismatch is safe for the current two-market
PAPER runtime but means the four-market ranking contract is not its runtime
allowlist.

Relevant sources: `services/paper_orchestration/certified_live_provider_readers.py:23-127`,
`services/underlying_registry.py:37-172`, and
`services/core/market_identity.py:4-42`.

## Ranking status

There are two ranking implementations outside the certified runtime path:

- `services/market_ranking_engine.py` is a legacy dictionary-oriented engine
  with a five-market list; it is not composed by the certified launcher.
- `services/opportunity_ranking/aggregate.py` provides a deterministic,
  supplied-candidate **four-market** ranking. Its policy requires exactly
  NIFTY/NSE, BANKNIFTY/NSE, FINNIFTY/NSE, and SENSEX/BSE; it orders eligible
  candidates, selects the first, and materializes market-specific eligibility,
  score, rank, blockers, warnings, and contradictions.

The four-market contract is structurally capable of retaining why a non-selected
market lost, but it cannot be invoked with only NIFTY and SENSEX: it requires
four candidates. `CertifiedLiveOpportunityAuthority` currently normalizes a
single option decision into one market’s READY/BLOCKED/CONFLICTING/FAILED/
NO_ACTION result and does not build a `MarketOpportunityCandidateV1` or call
either ranker.

Relevant sources: `services/market_ranking_engine.py:10-144`,
`services/contracts/four_market_ranking_policy_v1.py:7-57`,
`services/contracts/four_market_opportunity_ranking_result_v1.py:32-90`,
`services/opportunity_ranking/aggregate.py:24-133`, and
`services/paper_orchestration/certified_live_provider_readers.py:375-514`.

## Candle, option-chain, analysis, P6, P7, and P8 status

| Path | Current certified behavior | Two-market readiness |
| --- | --- | --- |
| Live quote / session | One quote and one session validation for the primary market | Provider identity supports both, scheduler uses one |
| Candles / analysis | `LiveMultiTimeframeData` fetches candles by supplied exchange and token; `LiveAnalysisPipeline` consumes that data | Parameterized for either selected market, no fan-out/batch alignment |
| Option chain | The opportunity reader passes the market spec’s option exchange; the builder reads the matching instrument universe and requests market data on that exchange | NFO and BFO routing is present; only one chain is requested per cycle |
| Opportunity | One option-decision result becomes one certified opportunity result | No per-market candidate collection or comparison |
| P6 | Automated mode accepts only an upstream exact certified P6 bundle; observe-only mode rejects planning | Safe fail-closed seam, but a selected-market ranking result is not supplied |
| P7 | New-entry lifecycle follows P6 and P8 admission; monitoring executor exists | Current composition supplies a factory that always raises “no active certified P7 position,” so monitoring is presently inert/failed rather than position-discovering |
| P8 | Persistence, admission, activation, and correlated-index limits are composed for automated PAPER | Portfolio guard can protect entries, but it does not perform market opportunity selection |

Relevant sources: `services/market/live_multi_timeframe_data.py:92-212`,
`services/live_analysis_pipeline.py:50-203`,
`services/live_option_chain_builder.py:177-225, 380-733`,
`services/live_option_decision_pipeline.py:801-891, 1375-1558`,
`services/paper_orchestration/certified_runtime_composition.py:332-451, 648-676,
846-905`, `services/paper_orchestration/complete_cycle_executor.py:68-563`, and
`services/paper_orchestration/existing_position_monitoring_cycle_executor.py:46-200`.

## Safety status

The certified composition is PAPER-only. It validates repository configuration
as PAPER enabled and live trading disabled, requires `execution_mode == "PAPER"`,
sets `live_execution_eligible` to false, and sets broker order submission to
false. Automated-PAPER composition separately validates that broker submission
remains disabled. The launcher provides signal-driven shutdown and structured
runtime logging. Runtime paths are created and write-probed as a startup
operation; this is operational I/O, not trade execution.

Relevant sources: `services/paper_orchestration/certified_runtime_safety.py:8-137`,
`services/paper_orchestration/certified_runtime_composition.py:764-784, 832-905`,
and `services/paper_orchestration/certified_runtime_launcher.py:58-171`.

## Monday-safe capabilities

- Start a PAPER-only certified launcher in observe-only mode, or explicitly
  opt into automated PAPER with the required typed authorities.
- Run a live-data-backed, safety-gated **single** NIFTY or **single** SENSEX
  opportunity cycle using the fixed certified market identity.
- Fetch market-specific candles and the corresponding NFO/BFO option chain;
  fail closed on missing or invalid data rather than submit a broker order.
- Persist PAPER P7/P8 artifacts and publish cycle results when the configured
  single-market automated path reaches those stages.
- Enforce no-live-execution and no-broker-submission invariants.

## Monday limitations

- Do not claim a NIFTY/SENSEX comparison: default operation evaluates only
  NIFTY, and a SENSEX configuration evaluates only SENSEX.
- No exact-once pair evaluation, common pair-level timestamp/skew policy, or
  two-market call-count guard exists.
- No certified two-market ranking, selected-market record, or rejected-market
  evidence is produced.
- The existing four-market ranker cannot substitute for this requirement
  because it requires four canonical candidates.
- Existing-position monitoring is wired to `_no_active_position_monitoring_input`,
  so the current composition does not discover and monitor persisted active P7
  positions.
- The composition’s recovery operation returns an empty successful result; it
  does not perform restart recovery of active positions.

## Mapping to the finalized two-market architecture

| Finalized architecture concern | Current implementation | Status |
| --- | --- | --- |
| Fixed universe: NIFTY/NSE + SENSEX/BSE | Exact provider and safety allowlists exist | Present |
| One coherent runtime cycle for both markets | One primary market becomes one `PaperOrchestrationCycleInputV1` | Missing |
| Independent live-data/candle/option evaluation for each market | Dynamic provider path works for either identity | Present as a single-market capability only |
| Evaluate both exactly once | No fan-out or pair coordinator | Missing |
| Compare only after both evaluations complete | No two-market candidate/result contract or aggregation point | Missing |
| Rank/select strongest eligible market | Isolated four-market ranker only; no runtime integration | Missing |
| Preserve the losing market’s reasons | Single result carries only the selected configured market’s evidence | Missing |
| Send only selected result to P6/P7/P8 | P6 receives one direct opportunity result | Missing selection boundary |
| Continue monitoring all persisted positions | Monitoring factory intentionally reports no active position | Missing runtime composition |
| Remain PAPER-only/fail closed | Multiple composition and authority guards enforce this | Present; preserve unchanged |

## Exact future Phase C changes

Phase C should implement the following, without widening the market universe
and without weakening PAPER-only guards:

1. Replace the single `primary_symbol` / `primary_exchange` runtime scheduling
   model with an immutable, ordered exact two-market universe:
   `(("NIFTY", "NSE"), ("SENSEX", "BSE"))`. Reject duplicates, omissions,
   unsupported identities, and configuration that silently falls back to one
   market.
2. Add a pair/batch cycle input and result boundary that records one parent
   cycle ID, a common requested-at time, both child observations, per-market
   receive/market timestamps, and an explicit timestamp-skew/freshness policy.
   Keep the existing immutable single-market input as the child contract where
   practical.
3. Replace `CertifiedCycleSource`’s one primary-market quote read with a
   two-market coordinator that creates exactly one child input for NIFTY and
   exactly one for SENSEX per parent opportunity cycle. Implement the finalized
   concurrency model explicitly (parallel fan-out with deterministic join, or
   documented sequential execution); current code implements neither pair
   model.
4. Run candle/analysis/option-chain/opportunity evaluation once per child
   identity, retain a per-market terminal result even when the other market is
   unavailable, and normalize both into a new exact two-market candidate/result
   contract.
5. Add a dedicated two-market ranker/policy, rather than adapting the required
   four-market contract. It must evaluate both candidates, rank only eligible
   candidates, select at most one winner, and retain each market’s score,
   eligibility, blockers, warnings, contradictions, and explicit
   selected/rejected rationale.
6. Make the P6 handoff consume only the selected eligible market’s certified
   evidence and preserve the complete two-market ranking result in the P6/P7/P8
   audit/journal metadata. If no candidate is eligible, emit a no-action parent
   result with both markets’ reasons and do not build P6 input.
7. Add selected-market-safe P7/P8 identifiers and portfolio admission wiring;
   preserve existing NIFTY/SENSEX correlated-risk controls and ensure an entry
   from one market cannot overwrite state for the other.
8. Replace `_no_active_position_monitoring_input` and the empty recovery stub
   with persisted-position discovery/recovery. Monitoring must group active
   positions by canonical identity and observe every active position, not only
   the currently selected opportunity market.
9. Add isolated, deterministic tests for both-exactly-once call counts,
   NIFTY/SENSEX routing, one-market failure, all-ineligible result, tie policy,
   selected-market-only P6 handoff, losing-market reason retention, P7/P8
   persistence, recovery, and PAPER/no-broker-submission invariants. These are
   Phase C work and were not run or implemented in this audit.

## Exact files inspected

- `run_continuous_paper_trading.py`
- `services/paper_orchestration/certified_runtime_launcher.py`
- `services/paper_orchestration/certified_runtime_composition.py`
- `services/paper_orchestration/certified_runtime_safety.py`
- `services/paper_orchestration/continuous_runtime_adapter.py`
- `services/paper_orchestration/certified_cycle_input_factory.py`
- `services/paper_orchestration/certified_live_provider_readers.py`
- `services/paper_orchestration/certified_live_read_authorities.py`
- `services/paper_orchestration/complete_cycle_executor.py`
- `services/paper_orchestration/deterministic_cycle_coordinator.py`
- `services/paper_orchestration/existing_position_monitoring_cycle_executor.py`
- `services/paper_orchestration/existing_position_monitoring_executor.py`
- `services/paper_orchestration/new_entry_paper_lifecycle_executor.py`
- `services/paper_portfolio/paper_portfolio_lifecycle_coordinator.py`
- `services/continuous_paper_trading_runtime.py`
- `services/core/market_identity.py`
- `services/underlying_registry.py`
- `services/market_ranking_engine.py`
- `services/opportunity_ranking/service.py`
- `services/opportunity_ranking/aggregate.py`
- `services/opportunity_ranking/eligibility.py`
- `services/contracts/four_market_ranking_policy_v1.py`
- `services/contracts/four_market_opportunity_ranking_result_v1.py`
- `services/live_analysis_pipeline.py`
- `services/market/live_multi_timeframe_data.py`
- `services/live_option_decision_pipeline.py`
- `services/live_option_chain_builder.py`
- `services/option_contract_ranking/ranking_pipeline.py`
- `services/contracts/market_opportunity_candidate_v1.py`
- `docs/P5_11A_FOUR_MARKET_OPPORTUNITY_RANKING_AUDIT.md`
- `docs/architecture/CANONICAL_FOUR_MARKET_UNIVERSE.md`
