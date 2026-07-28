# P5 intelligence roadmap

P5 builds a trustworthy four-market intelligence layer for NIFTY/NSE,
BANKNIFTY/NSE, FINNIFTY/NSE, and SENSEX/BSE. It does not change certified
P3/P4 execution semantics, enable live execution, or migrate dashboards early.

P5-0 is complete: READY_WITH_BLOCKERS. P5-1 is certified. P5-2 is certified.
P5-3 and P5-4 are certified; P5-5 option-chain intelligence is next. No
provider migration or P3/P4 behavior change occurred in P5-4.
P5-3 is certified: canonical structural multi-timeframe intelligence is
available. P5-4 technical pillar remains next. P5-2 is certified:
provider-neutral quality/freshness is available. P5-3 multi-timeframe
intelligence remains next. P5-1 establishes the
immutable static universe. P5-2 provides provider-neutral
quality/freshness contracts. P5-3 adds canonical multi-timeframe snapshots.
P5-4 technical, P5-5 option-chain, P5-6 broader/correlation, P5-7 global/
institutional/sentiment/events, P5-8 regime, and P5-9 ranking each add bounded
contracts, injected runtime APIs, negative tests, and certification gates.
P5-10 supplies replay/certification.

Dependencies are strictly P5-1 → P5-2 → P5-3 → P5-4/5/6/7 → P5-8 → P5-9 →
P5-10. Retain legacy providers behind adapters; use shadow comparison rather
than replacement. P4 assumes explicit, paper-only, manually authorized inputs;
P6 may consume only certified P5 results. No persistence, provider calls at
import, background work, automatic execution, or dashboard migration is in
scope for P5 core.

P5-1 does not migrate live providers or change P3/P4 semantics; P5-2 remains
the next phase after certification.
