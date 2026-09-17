# P10A Dashboard Authority Audit

## Active boundary

The active application path is `app.py` → `dashboard.dashboard_v2.home`.
`dashboard_v2.py` synchronizes a registered immutable publication into
Streamlit session state and renders view objects. It has no provider import,
analysis/ranking/option-selection/risk/trade-plan call, persistence write,
PAPER mutation, broker control, or refresh loop. Its session-state updates are
UI-local copies of published models, not persistence writes.

## File findings

| File | Finding |
| --- | --- |
| `dashboard/dashboard_v2.py` | Active display-only renderer; reads publication state and calls render helpers. |
| `dashboard/dashboard_publication_sync.py` | Display-state synchronizer; reads process-local publication snapshot and copies immutable views into Streamlit state. No provider or persistence mutation. |
| `dashboard/plan_position_components.py` | P6/P7 presentation only; formats supplied view fields and fill history. |
| `dashboard/operational_components.py` | Option/runtime presentation only. |
| `dashboard/dashboard_read_model_state.py`, `dashboard/dashboard_operational_read_model_state.py` | Exact-type session-state accessors only. |
| `dashboard/home.py` | Legacy, non-active violation: direct market fetch, market overview, technical calculation, AI, trade recommendation, and summary construction. |
| `dashboard/live_market_test.py` | Legacy diagnostic violation: direct snapshot fetch plus trend/trade/confidence calculations. |
| `dashboard/sidebar.py` | Legacy presentation helper with text input and refresh button; no broker control, but user-selected symbols are not a certified runtime selector. |
| `dashboard/widgets.py`, `layout.py`, `charts.py` | Presentation/layout/chart helpers; no certified runtime authority. |
| `app.py` | Streamlit entry/session initialization only; no refresh loop or trading operation. |

## Requested responsibility audit

| Concern | Active dashboard | Legacy files |
| --- | --- | --- |
| Direct provider calls | No | `home.py`, `live_market_test.py` |
| Indicator/trading computation | No | `home.py`, `live_market_test.py` |
| Ranking, option selection, risk, P6 plan construction | No | `home.py` indirectly builds a legacy trade recommendation; not P6 authoritative |
| Direct persistence/PAPER lifecycle mutation | No | None in dashboard files found |
| Refresh loops | No | No loop; legacy sidebar has an unused refresh button |
| Operator/broker controls | No | None found |
| Duplicated business logic | Active path no; legacy pages duplicate non-authoritative analysis/trade presentation | `home.py`, `live_market_test.py` |

## Authoritative PAPER sources

The dashboard consumes only published, immutable projections.  The certified
PAPER authorities remain outside Streamlit and the read-model package:

- P7 position persistence: `PaperTradePersistenceService`
- P8 portfolio persistence: `PaperPortfolioPersistenceService`
- P9 cycle result: `PaperOrchestrationCycleResultV1`
- Runtime status: `ContinuousPaperTradingRuntime.get_stats()`

Legacy trade-statistics or database views are diagnostic only and must not
replace these authorities.

## Result

The active Streamlit dashboard is already display-only relative to the P10
publication boundary. Legacy pages must remain non-authoritative or be removed
from navigation; they must not be reused for the certified PAPER dashboard.
No dashboard code was changed in this audit.

Relevant sources: `dashboard/dashboard_v2.py`,
`dashboard/dashboard_publication_sync.py`,
`services/dashboard_publication/*`, and `services/dashboard_read_models/*`.
