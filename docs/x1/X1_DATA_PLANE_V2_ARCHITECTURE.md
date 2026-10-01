# X1 Data Plane V2 - Architecture and Operational Notes

## 1. Scope

X1 is a read-only, zero-authority data plane for the five-market
universe (NIFTY, SENSEX, CRUDEOILM, GOLDM, NATGASMINI). It ingests
FYERS market data, normalizes it, classifies it per instrument,
publishes valid quotes into a shared hub, and produces deterministic
replayable observation records.

X1 has no order, execution, decision, risk, position, broker, or
certification authority. It does not touch any trading entrypoint,
PAPER execution, Task9 collector, certification record, or frozen
Brain V1 contract.

## 2. Module map

services/x1/
  observation_identity_v1.py       Deterministic observation identity
  observation_tracker_v1.py        Per-instrument quality classification
  streaming_hub_bridge_v1.py       Classify-then-publish bridge
  composition_v1.py                Opt-in streaming-to-hub wiring + rollover
  observation_journal_v1.py        Versioned JSONL journal + deterministic replay
  fyers_request_controller_v2.py   Bounded request controller over existing limiter
  endpoint_cache_v1.py             Bounded LRU REST cache with endpoint TTLs
  instrument_rollover_v2.py        Data-subscription rollover primitives

Additive changes to existing files:
  services/broker/fyers_streaming_v2.py
    connection-generation-bound callbacks, tri-state readiness,
    reconnect diagnostics.
  services/broker/shared_market_data_hub_v2.py
    invalidate_instrument.
  src/rate_limiter.py
    opt-in max_wait_seconds bounded wait.

## 3. Data flow

FYERS DataSocket (or fake)
  -> FyersStreamingDataProviderV2._on_message_for_socket
     drops foreign/closed/not-ready callbacks; stamps connection_generation
  -> X1DataPlaneCompositionV1._on_tick
     reads current_generation from streaming.snapshot()
  -> ObservationTrackerV1.classify
     STALE_GENERATION / SUSPECTED_DUPLICATE / OUT_OF_ORDER
     FUTURE_DATED / STALE_DATED / MALFORMED / VALID
  -> if VALID: StreamingHubBridgeV1._build_quote
     MarketQuoteV2(source_type="LIVE", is_cached=False)
     SharedMarketDataHubV2.publish_quote
  -> if journal provided: ObservationJournalV1.append
     ObservationRecordV1 canonical JSONL
     replay via ObservationJournalV1.load(replay_at=...)

## 4. Schema versions

X1_OBSERVATION_IDENTITY_V1
X1_OBSERVATION_RECORD_V1
X1_OBSERVATION_QUALITY_V1 (values carried inline)

## 5. Safety invariants

- Every X1 class declares data_only = True,
  order_capability_allowed = False,
  automatic_fallback_allowed = False.
- No X1 module imports fyers_apiv3, SmartApi, yfinance, dotenv,
  requests, urllib, http, or socket.
- No X1 module reads os.environ / os.getenv.
- No X1 module monkey-patches DNS or sockets.
- Importing any X1 module performs no network I/O and writes no stdout
  or stderr.
- No X1 module writes to data/task9/, data/rate_limit/state.json,
  logs/supervisor/, or any certification record.

## 6. Operational runtime root

The X1 observation journal takes an explicit session root. Recommended
deployed layout:

  data/x1/observations/<YYYY-MM-DD>.jsonl

The .gitignore contains a narrow entry for data/x1/observations/ so
runtime journal files are never committed.

## 7. Reconnect and generation ambiguity

The FYERS SDK does not expose a per-message generation identifier.
X1 tags every record with the generation that was current when the
callback fired. On a same-socket reconnect, on_connect bumps the
generation and every subsequent callback is tagged with the new one.
X1 cannot distinguish a callback captured before the reconnect from
one captured after, when both arrive on the same socket instance.

X1 does not claim stronger guarantees than this. It only:
- tags messages with a generation,
- refuses messages explicitly stamped with a stale generation
  (ObservationTrackerV1),
- exposes reconnect diagnostics on the streaming snapshot:
  reconnect_count, first_connected_at, last_reconnected_at.

## 8. Subscription rollover

X1DataPlaneCompositionV1.rollover(previous_instrument, resolver, as_of):

1. Resolve replacement via resolve_instrument_replacement_v2.
   Underlyings are never eligible.
2. NOT_EXPIRED / UNAVAILABLE / AMBIGUOUS: no subscription change.
3. REPLACED: subscribe new instrument first. On failure: no change.
4. New-subscribe OK: unsubscribe old subscription. On failure:
   attempt to unsubscribe the new one and return ROLLBACK.
5. Both OK: invalidate old instrument cache via
   invalidate_from_rollover_v2 (which calls
   SharedMarketDataHubV2.invalidate_instrument).
6. Update tracked current instrument; append to rollover history.

Trading-position rollover is a separate responsibility. X1 does not
alter any open PAPER position.

## 9. Bounded resources

- ObservationTrackerV1: max_instruments (default 512).
- ObservationJournalV1: max_records_per_file (default 100000) and
  max_file_bytes (default 268435456). No rotation.
- EndpointCacheV1: max_entries (default 1024).
- FyersRequestControllerV2Impl: max_attempts (default 3) and
  max_wait_seconds (default 30).

## 10. What X1 does not claim

- No live FYERS connectivity has been exercised; all validation is
  offline.
- No power-loss durability; the journal does not fsync.
- No end-to-end FYERS Retry-After semantics validation.
- No exact count of lost messages when the provider exposes no
  sequence information.

## 11. Integration points

- SharedProviderOrchestratorV2: X1 does not install itself.
- ProviderRequestControllerV2: FyersRequestControllerV2Impl
  structurally satisfies the protocol and wraps
  FyersRateLimitCoordinator.
- ProviderRuntimeBundleV2: unchanged.

## 12. Deferred work (out of X1)

X2 constituent intelligence.
X3-X8 feature engines.
X9 MarketSnapshotV2.
X10 Shadow Brain V2.
B5 Risk Governor and subsequent phases.
