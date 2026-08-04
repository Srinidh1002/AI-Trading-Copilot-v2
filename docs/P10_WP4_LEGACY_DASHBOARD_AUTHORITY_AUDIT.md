# P10-WP4 — Remaining Legacy Dashboard Authority Audit

## Objective

Remove every remaining data-acquisition, analysis, persistence, performance,
health-check, and trading-statistics authority from the active Streamlit
dashboard. The active dashboard must become a pure renderer of immutable,
pre-published dashboard read models.

## Current active legacy authorities

`dashboard/dashboard_v2.py` still initiates:

- direct SQLite access to `database/ai_trading.db` and `decision_log`
- legacy market snapshot acquisition
- dashboard-side analysis and presentation transformation
- legacy paper-trade statistics acquisition
- performance monitor reads
- health-check execution
- history-cache and `safe_execute` service calls
- mixed rendering of legacy decision state and certified P6/P7 state

## Target architecture

PAPER runtime and certified producers
→ immutable dashboard publication envelopes
→ thread-safe last-known-good publication stores
→ Streamlit session-state synchronization
→ pure rendering components

The active Streamlit dashboard must not import or invoke SQLite, Pandas data
access, market snapshot services, analysis/trade engines, option engines,
paper-trade managers, persistence, caches, performance monitors, health
services, runtime, or orchestration.

## Work packages

1. WP4-1 — audit and policy
2. WP4-2 — market and option overview read models
3. WP4-3 — validation, history, performance, and health read models
4. WP4-4 — authoritative publication integration
5. WP4-5 — pure rendering extraction
6. WP4-6 — active dashboard authority removal
7. WP4-7 — certification

## Failure policy

- no publication: explicit unavailable state
- transient producer failure: preserve last-known-good and expose warning
- stale publication: retain and mark stale
- malformed state: fail closed
- Streamlit rerun: never initiates authoritative work

## PAPER safety

P10-WP4 does not place broker orders, authorize LIVE execution, calculate new
entry/stop/target values, mutate lifecycle or portfolio state, write
persistence, or run market acquisition from Streamlit.
