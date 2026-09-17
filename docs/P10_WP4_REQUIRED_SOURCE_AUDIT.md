# P10-WP4 — Required Source Audit

Inspect the exact current repository versions of:

- `dashboard/dashboard_v2.py`
- `services/dashboard/dashboard_analysis_service.py`
- `services/market_snapshot.py`
- `services/trade/paper_trade_manager.py`
- `services/performance.py`
- `services/health/health_check.py`
- the module exporting `history_cache`
- authoritative P7/P8 persistence/result contracts
- authoritative runtime statistics/result contracts
- current `app.py`

The audit must determine which certified result owns market overview, decision,
trend/pattern/support/resistance, option intelligence, wins/losses/P&L,
history, performance, and health evidence. Any legacy section with no
certified source must become explicitly unavailable rather than inferred.
