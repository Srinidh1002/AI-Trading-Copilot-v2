# P10B Monday-Safe Read-Model Design

## Design rule

The Streamlit layer receives immutable published views and renders them. It
must not fetch providers, run analysis, rank markets, select options, calculate
risk, construct a plan, mutate P7/P8, write a journal, or expose broker/order
controls.

## Existing boundary and minimal contract

Existing P10 publication contracts already carry opportunity, P6 plan, P7
position, option intelligence, and runtime operations. This work adds only
`DashboardTwoMarketRuntimeViewV1`: an immutable, PAPER-only display summary.
It is deliberately not wired into the publication envelope or Streamlit yet.

The contract covers: runtime safety, provider freshness, NIFTY/SENSEX status,
selected market when present, latest opportunity/P6 statuses, pending/open P7
counts, P8 status, latest PAPER actions, last successful/failing cycle,
emergency halt, broker submission status, and live eligibility.

`selected_market` is optional and means “published by an upstream authority.”
The current runtime does not publish true NIFTY-vs-SENSEX selection, so it must
normally remain absent rather than be inferred by the UI.

## Source-to-view mapping

| Read field | Future authoritative producer |
| --- | --- |
| Runtime safety, emergency halt, broker/live flags | Certified launcher controls and safety configuration |
| Provider freshness, last successful/failure | P9 cycle result plus runtime publication producer |
| NIFTY/SENSEX status, selected market | Future Phase C pair coordinator/ranking result only |
| Latest opportunity/P6 plan | Published P5/P6/P9 typed result |
| Pending/open P7, latest PAPER actions | P7 persistence snapshot and cycle result |
| P8 portfolio | P8 persistence snapshot/projection |

## Exact next P10 integration boundary

`P5/P6/P7/P8/P9 typed snapshots + future Phase C two-market result`
→ `pure projection adapter (one input read each, caller-supplied timestamps)`
→ `DashboardTwoMarketRuntimeViewV1`
→ `DashboardPublicationEnvelopeV1 extension`
→ `DashboardPublicationStore`
→ `dashboard_publication_sync.py`
→ `dashboard/dashboard_v2.py` rendering.

The projection adapter—not Streamlit—will own source validation, stale/missing
state representation, and deterministic field projection. It must not invoke
providers or mutate state. Envelope/UI wiring is intentionally deferred until a
single upstream source can truthfully supply both-market and selected-market
data.

## Safety and freshness policy

- Preserve `PAPER`, `live_execution_eligible=false`, and
  `broker_order_submission=false`; reject unsafe contract construction.
- Missing state remains explicit (`None`/zero count/status), never fabricated.
- Last failure and last successful cycle are independent fields; an outer cycle
  completion must not erase an inner fail-closed state.
- A no-trade/no-action status is informational and valid.
- No refresh loop belongs in Streamlit. Runtime publication is the refresh
  authority; Streamlit only consumes the latest registered snapshot.
