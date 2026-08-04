# P2-7 — CLI Canonical Migration and Paper Separation

## Targeted trace

The current root entry point is `live_option_decision_nifty.py`. Its historical
path constructs `AngelMarketDataClient`, validates spot data, invokes
`LiveOptionDecisionPipeline.analyse`, saves dashboard/audit state, and sends
the result to `PaperTradingOrchestrator.process_decision`. That orchestrator can
persist via `PaperTradeRepository`. Its decisions, option selection, session
gates, paper flags, stdout, and exit paths are monolithic in the script.

The existing explicit dashboard paper boundary is separately
`services.trade.trade_engine.execute_paper_trade`; it validates then calls
`services.trade.paper_trade_engine.process_trade`, which can write through the
paper-trade manager.

## P2-7 migration boundary

Direct CLI execution now defaults to the explicit canonical command service in
`services.canonical.live_option_cli_service`. It accepts supplied snapshot,
decision, and candidate JSON artifacts and separates `analyse`, `prepare-paper`,
and `execute-paper`. The historical root path is retained only when the narrow
non-secret `CLI_ANALYSIS_MODE=legacy` rollback mode is selected.

`CLI_ANALYSIS_MODE=compare` emits canonical-vs-legacy diagnostics for the same
supplied snapshot. It keeps canonical output official. The migration setting
does not grant any authorization.

## Paper policy

New `PaperTradeCandidateV1` and `services.paper.paper_candidate_service` keep
preparation and execution distinct. Current canonical decisions remain
analysis-only and plan-free, so preparation returns `NEEDS_TRADE_PLAN`; no
candidate, position, database write, or execution follows. Future explicit
submission still requires matching identity, freshness, `PAPER_READY`,
`NOT_REQUESTED`, and manual approval before the existing paper executor can be
called. No live broker is available through this boundary.

## Files changed

- `live_option_decision_nifty.py`
- `services/canonical/live_option_cli_service.py`
- `services/contracts/paper_trade_candidate_v1.py`
- `services/contracts/__init__.py`
- `services/paper/__init__.py`
- `services/paper/paper_candidate_service.py`
- focused candidate/preparation tests
- `docs/contracts/PAPER_TRADE_CANDIDATE_V1.md`
- this audit record and `docs/CHANGELOG.md`

## Verification status

Per P2-7 instructions, no pytest, coverage, lint, formatting, CLI command,
Streamlit, broker API, market-data provider, or external service was run.
