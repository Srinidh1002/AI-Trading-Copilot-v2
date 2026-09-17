# P5-12 Full Intelligence Replay and Certification

## P5-12A Full intelligence fixture architecture

P5-12A supplies deterministic, PAPER-only typed fixture builders for the four
canonical markets, fixed UTC timebase, scenario vocabulary, technical and
option-chain intelligence, broader/external context, canonical regime, trade
opportunity, candidate, and public four-market ranking assembly. Fixture
modules are isolated from providers and runtime behavior. Tests cover
architecture, determinism, and isolation. No production code changes are part
of P5-12A. P5-12B remains pending.

### P5-12A.1 scenario capability repair

P5-12B design exposed fixture-only capability gaps. P5-12A.1 repairs
deterministic broader-market and external-context profiles, and aligns
regime/candidate unavailable handling so all nine scenario families construct
through the complete fixture stack. No production code changes are included;
P5-12B remains pending until its focused boundary is green.

### P5-12A.2 quality and freshness provenance repair

P5-12C exposed a fixture timestamp-propagation gap. The public fixture API now
accepts deterministic per-component source timestamps and provides immutable
fresh, delayed, stale, future, and mixed profiles. Typed layer builders expose
their assigned timestamps; candidate freshness and source-timestamp fields stay
coherent, including delayed evidence represented through a supported candidate
state and warning. Optional, missing-required descriptor, and provider-blocked
fixture seams are available without production changes. Four-market helpers now
accept per-market provenance mappings. P5-12C remains pending until its focused
fixture boundary is green.

Freshness-profile keys are documented lowercase fixture keys. The exported
`to_candidate_source_timestamps()` helper explicitly converts them to the
uppercase vocabulary normalized by `MarketOpportunityCandidateV1`; caller
mappings remain unchanged.

### P5-12A.3 quality and freshness replay seams

P5-11 eligibility treats candidate freshness fields as already classified;
`source_timestamps` are diagnostic and P5-11 does not calculate age, future
tolerance, or skew from them. P5-12A.3 therefore adds fixture-only immutable
component quality and freshness profiles, plus a deterministic profile
classifier used solely to prepare certified candidate states for replay.
Optional and required failures remain distinct, including provider-blocked
evidence; present partial option-chain, broader-market, and external-context
evidence uses certified warning states. Liquidity and execution-quality
timestamps are fixture-owned provenance inputs mapped only into existing
candidate availability and warning fields. A safe missing-required evaluator
descriptor supports aggregate-boundary tests without invalid candidate
construction. Four-market helpers accept independent per-market profiles. No
production changes are included; P5-12C remains pending until this regression
boundary is green.

## P5-12B full-stack directional replay

P5-12B adds deterministic public-fixture replay coverage for all nine scenario
families across all four canonical markets, directional strong/weak relations,
homogeneous matrices, every-market bullish/bearish winner matrices, and
fail-closed blocked/unavailable/conflicting behavior. It verifies typed stack
identity alignment, PAPER-only outputs, ranking slot preservation, deterministic
serialization, and selection confidence. No production code is changed.

## P5-12C Quality and freshness replay

P5-12C adds `test_p5_12c_quality_freshness_replay.py`,
`test_p5_12c_four_market_quality_matrix.py`, and
`test_p5_12c_quality_freshness_regressions.py`. The suite replays 32 typed
single-market cases across fresh, delayed, stale, future, mixed, partial,
missing-optional, and provider-blocked profiles, plus safe evaluator-reported
missing-required cases. Fixture timestamp classification remains distinct from
P5-11 eligibility, which consumes the resulting candidate state rather than
calculating age or skew. Coverage includes required-versus-optional failures,
partial typed evidence, fixture-owned liquidity/execution provenance, exact
age/future/skew boundaries, four-market quality matrices, one-time penalties,
denominator compatibility, deterministic serialization/order independence, and
PAPER-only restrictions. No production or fixture changes are included;
P5-12D remains pending.

### P5-12A.4 event and session replay seams

P5-12D exposed missing event/session propagation. P5-12A.4 adds fixture-only
event and session descriptors, typed external event-risk context, deterministic
market-session validation, and candidate/regime mappings that preserve event
warnings, event blockers, and session restrictions separately. Overlap keeps
all reasons with blocking precedence. Four-market helpers accept independent
per-market event and session profiles. No production changes are included;
P5-12D remains pending until this regression boundary is green.

## P5-12D Event and session replay

P5-12D adds `test_p5_12d_event_session_replay.py`,
`test_p5_12d_four_market_event_matrix.py`, and
`test_p5_12d_event_session_regressions.py`. It covers 44 deterministic
single-market event/session replays for RBI, Union Budget, CPI, election,
holiday, special sessions, weekly and monthly expiry, rollover, overlapping
events, and combined event/session restrictions. Tests preserve typed event and
session provenance, event-versus-session separation, one-time event penalties,
four-market ordering, determinism, no mutation, and PAPER-only output. No
fixture or production files are changed by P5-12D; P5-12E remains pending.

## P5-12E Four-market ranking replay

P5-12E adds `test_p5_12e_four_market_ranking_replay.py`,
`test_p5_12e_ranking_ties_and_order.py`, and
`test_p5_12e_ranking_replay_regressions.py`. Coverage proves every market can
win, rejected candidates never win, conflicts remain visible, ties and
near-ties are deterministic, candidate order is irrelevant, and mixed-validity
and all-ineligible results preserve every market slot. Ranking score, group,
serialization, no-mutation, and PAPER-only constraints are covered. Fixtures
and production remain unchanged; P5-12F is pending.

## P5-12F Determinism and serialization certification

P5-12F adds `test_p5_12f_repeated_output_equality.py`,
`test_p5_12f_serialization_stability.py`, and
`test_p5_12f_order_mutation_randomness.py`. The certification covers repeated
full-stack and layer-by-layer equality, stable JSON and semantic dictionaries,
input-order independence, caller-input and detached-output no-mutation, stable
IDs and fixed timestamps, fresh-subprocess and `PYTHONHASHSEED` independence,
and source checks rejecting random, UUID, and current-time generation. It also
certifies deterministic ties, all-ineligible outcomes, event ordering, and
PAPER-only restrictions. Fixtures and production files remain unchanged;
P5-12G remains pending.

## P5-12G Isolation and architectural certification

P5-12G adds `test_p5_12g_import_isolation.py`,
`test_p5_12g_architecture_boundaries.py`, and
`test_p5_12g_subprocess_isolation.py`. These tests certify direct and
transitive import isolation, provider and broker/execution isolation,
dashboard/Streamlit and AI/news isolation, network and filesystem isolation,
randomness/current-time rejection, environment independence, relevant
`sys.modules` footprints, and the fixture-to-contract/ranking architecture
direction. They also audit public API use and semantic monkeypatching, confirm
PAPER-only fields are passive data with live execution disabled, and retain the
headless, deterministic replay boundary. Fixtures and production remain
unchanged. P5-12H final results are recorded below.

## P5-12H P5 regression certification

### Certification boundaries

P5-8 focused, P5-9 focused, P5-10 focused, P5-11 focused, complete P5-12,
full intelligence, TradeOpportunity, and the full-repository suite all passed.

### Exact commands

```powershell
# P5-8 focused suite
venv\Scripts\python.exe -m pytest tests\test_p5_8*.py -q
# P5-9 focused suite
venv\Scripts\python.exe -m pytest tests\test_p5_9*.py -q
# P5-10 focused suite
venv\Scripts\python.exe -m pytest tests\test_p5_10*.py -q
# P5-11 focused suite; see its exact Group 1 inventory above in this document.
venv\Scripts\python.exe -m pytest tests\test_p5_11*.py -q
# Complete P5-12A--G suite, each current file exactly once.
venv\Scripts\python.exe -m pytest `
tests/test_p5_12a_fixture_determinism.py `
tests/test_p5_12a_fixture_isolation.py `
tests/test_p5_12a_full_intelligence_fixture_architecture.py `
tests/test_p5_12b_four_market_directional_matrix.py `
tests/test_p5_12b_full_stack_directional_replay.py `
tests/test_p5_12b_full_stack_replay_regressions.py `
tests/test_p5_12c_four_market_quality_matrix.py `
tests/test_p5_12c_quality_freshness_regressions.py `
tests/test_p5_12c_quality_freshness_replay.py `
tests/test_p5_12d_event_session_regressions.py `
tests/test_p5_12d_event_session_replay.py `
tests/test_p5_12d_four_market_event_matrix.py `
tests/test_p5_12e_four_market_ranking_replay.py `
tests/test_p5_12e_ranking_replay_regressions.py `
tests/test_p5_12e_ranking_ties_and_order.py `
tests/test_p5_12f_order_mutation_randomness.py `
tests/test_p5_12f_repeated_output_equality.py `
tests/test_p5_12f_serialization_stability.py `
tests/test_p5_12g_architecture_boundaries.py `
tests/test_p5_12g_import_isolation.py `
tests/test_p5_12g_subprocess_isolation.py `
-q
# Full intelligence regression
venv\Scripts\python.exe -m pytest tests\test_*intelligence*.py -q
# TradeOpportunity regression
venv\Scripts\python.exe -m pytest tests\test_trade_opportunity_v1.py tests\test_trade_opportunity_integration.py tests\test_four_index_trade_opportunity.py tests\test_option_contract_ranking_evaluator.py tests\test_option_contract_ranking_pipeline.py tests\test_option_contract_ranking_policy_v1.py tests\test_option_contract_ranking_ranker.py tests\test_option_contract_ranking_result_v1.py -q
# Full repository suite
venv\Scripts\python.exe -m pytest -q
```

### Results

| Boundary | Passed | Failed | Skipped | Warnings | Duration | Exact pytest summary |
| --- | ---: | ---: | --- | --- | ---: | --- |
| P5-8 focused suite | 205 | 0 | not reported | not reported | 15.08s | `205 passed in 15.08s` |
| P5-9 focused suite | 182 | 0 | not reported | not reported | 10.40s | `182 passed in 10.40s` |
| P5-10 focused suite | 516 | 0 | not reported | not reported | 3.40s | `516 passed in 3.40s` |
| P5-11 focused suite | 77 | 0 | not reported | not reported | 4.35s | `77 passed in 4.35s` |
| Full P5-12 suite (21 files) | 318 | 0 | not reported | not reported | 5.56s | `318 passed in 5.56s` |
| Full intelligence regression (26 files) | 1,793 | 0 | not reported | not reported | 9.90s | `1793 passed in 9.90s` |
| TradeOpportunity regression | 227 | 0 | not reported | not reported | 0.99s | `227 passed in 0.99s` |
| Full repository suite | 12,908 | 0 | not reported | 2 | 74.14s | `12908 passed, 2 warnings in 74.14s (0:01:14)` |

### Architecture confirmation

Evidence covers deterministic canonical fixtures; directional, quality/freshness
and event/session replay; four-market ranking; deterministic serialization;
import isolation; no provider/broker/execution/dashboard/AI/network dependency;
no random/UUID/current-time generation; and PAPER-only results with live
execution disabled. This is deterministic PAPER-mode validation, not approval
for live execution.

### Final P5 decision

**P5 CERTIFIED COMPLETE.** All eight required regression boundaries passed,
including the final repository suite with 12,908 passing tests and two reported
warnings. No production files were modified during P5-12. Certification covers
deterministic PAPER-mode intelligence validation; live execution remains
disabled, and this is not approval for live trading.

After certification, review and stage only the P5-12 fixture/tests and this
document, then run:

```powershell
git status --short
git add tests/fixtures/p5_12 tests/test_p5_12a_*.py tests/test_p5_12b_*.py tests/test_p5_12c_*.py tests/test_p5_12d_*.py tests/test_p5_12e_*.py tests/test_p5_12f_*.py tests/test_p5_12g_*.py docs/P5_12_FULL_INTELLIGENCE_CERTIFICATION.md
git diff --cached --stat
git diff --cached --check
git commit -m "Complete P5 intelligence replay and certification"
```
