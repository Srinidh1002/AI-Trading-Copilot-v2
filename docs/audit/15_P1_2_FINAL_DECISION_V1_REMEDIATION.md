# P1-2 FinalDecision v1 Remediation

## Audit inventory

Decision producers include `services/trade/trade_engine.py`/`services/trade/trade_response_builder.py`, the root and package master-decision engines, `services/unified_decision_engine.py`, `services/core/final_decision_pipeline.py`, and `services/live_option_decision_pipeline.py`. Dashboard consumes the trade response (`decision`, approval flags, confidence, plan, trend/risk presentation). Paper execution consumes approved directional payloads and plan fields. Audit/reporting consume legacy decision/status strings, reasons, selected contract, audit trail, and timestamps. Live CLI emits session/data blocks, `NO_TRADE`, `TRADE_READY`, `TRADE_ALLOWED`, and `TRADE_REJECTED` with optional plan/contract/audit data.

Legacy vocabularies mix recommendations (`BUY`, `SELL`, `BUY CE`, `BUY PE`, `HOLD`, `WAIT`, `NO_TRADE`), authorization/lifecycle states (`TRADE_READY`, `TRADE_ALLOWED`, `TRADE_REJECTED`), and market/data states (`MARKET_CLOSED`, `MARKET_HOLIDAY`, `STALE_MARKET_DATA`, `ERROR`). They are intentionally not migrated here.

## Canonical contract

`services/contracts/final_decision_v1.py` separates action, authorization, execution, plan, risk, evidence, options interpretation, data health, and audit metadata. It is not routed into dashboard, paper, or live paths. Legacy adapters map only verified direction/plan/approval information and block ambiguous inputs. The contract cannot invoke `process_trade`, execution, or providers.

## Compatibility limitation

Legacy responses often omit a snapshot ID, canonical instrument identity, complete trade plan, data health, or a semantically reliable authorization signal. The adapters preserve what is available, record unmapped fields, and block rather than fabricate missing safety evidence.

## Verification

Focused FinalDecision v1 coverage passed 38 parametrized cases. FinalDecision/MarketSnapshot/P0 safety coverage passed 93 tests with the two existing third-party SSL deprecation warnings. The full configured suite collected 2,708 tests: 2,697 passed, 11 failed, 0 skipped, and 2 warnings in 12.73 seconds. The failures exactly match the certified P1-1 baseline: broker empty-response/cache expectations, the `LiveAnalysisPipeline` constructor mismatch, six `LiveMultiTimeframeData(cache=...)` constructor mismatches, and injected-client wiring in `LiveOptionDecisionPipeline`.
