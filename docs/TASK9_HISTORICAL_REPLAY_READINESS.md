# Task 9 historical replay readiness

## Reusable components

- `LiveMultiTimeframeData` with cache, closed-candle coverage, typed failures,
  durable gate, and cooldown.
- `capture_certified_live_evidence` and canonical candidate evaluation.
- Task 8 exact two-market parent/child orchestration and Task 9 typed handoff.
- PAPER planning, lifecycle, outcome, reconciliation, receipt persistence, and
  read-only dashboard publication.

## Replay adapter

`Task9HistoricalCertificationReplay` accepts an explicit trading date and
create separate NIFTY/SENSEX historical cycle inputs with source provenance
`HISTORICAL_REPLAY`. It must use completed candles only, retain source and
timestamp truth, and use later historical candles only for deterministic
outcome evaluation.

## Gaps / constraints

- Current Task 9 counting evaluator is intentionally live-run bound; replay
  must have a separate non-countable receipt/report authority.
- Live quote and option FULL/Greeks requirements need a replay-compatible
  evidence policy rather than synthetic current quotes.
- The legacy completed-candle direct fetch must not be used by replay; reuse
  the certified historical service.
- Replay needs date/session calendar authority and restart/idempotency keys
  separate from `official_run_id`.

The adapter has an injected completed-session reader only: it has no Angel
client, no live launcher dependency, and writes idempotent atomic receipts only
under `data/paper_trading/certified_runtime/task9_historical_replay/`. Its
canonical source is `HISTORICAL_REPLAY`; all receipts are explicitly PAPER,
non-counting, broker-submission false, and live-execution-ineligible.

`task9_session_independent_readiness.py` is the after-hours command. It accepts
only `--evidence-file` offline JSON evidence; there is deliberately no provider
mode. It replays twice against the separate store and reports a non-zero status
when safety or replay readiness fails.
