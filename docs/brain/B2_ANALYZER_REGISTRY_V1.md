# B2 Analyzer Registry V1

## Purpose

The analyzer registry records the analysis families discovered during B1 and
provides a stable inventory for future zero-authority adapters.

Registration is metadata. Registration is **not authority**.

## B1 production finding

The currently running production paths are not unified:

### NIFTY / SENSEX

Production reaches the existing index runtime and `src/mtf_enhanced.py`.

The current index family includes:

- previous session;
- gap;
- global risk;
- India VIX;
- institutional flow;
- news;
- legacy event calendar;
- breadth;
- legacy MTF technical analysis;
- regime;
- option-chain evidence.

### MCX

Production reaches the MCX-native stack, including:

- MCX MTF;
- regime;
- structure/VWAP;
- Price/OI;
- stable PCR and max pain;
- commodity event risk.

### Canonical technical intelligence

`services/technical_intelligence` has independently verified indicator
mathematics for EMA, RSI, MACD, ADX, ATR and Bollinger.

B1 established that this canonical package is **not currently on the
production-authoritative execution path** for NIFTY, SENSEX or MCX.

It is therefore registered as `SHADOW_AVAILABLE`, not as a production input.

## Registry responsibilities

The registry describes:

- analyzer identity/version;
- supported markets;
- evidence category;
- source family;
- whether B1 observed the analyzer as currently consumed by production;
- whether an adapter is required;
- expected output contract.

## Explicitly excluded authorities

The analyzer registry does not own and must never silently acquire:

- data-quality admission authority;
- risk limits;
- capital allocation;
- broker submission;
- execution;
- order management;
- position management;
- certification counting;
- policy promotion;
- supervisor lifecycle.

Those remain separate safety/control planes.

## Known semantic issues retained for later normalization

### Index PCR

B1 found that index and MCX PCR semantics are not directly comparable.

The registry therefore records the analyzer families without pretending that
their numeric values share identical directional meaning.

Normalization belongs in a later adapter contract and must preserve the raw
value plus the source engine's original interpretation.

### Event intelligence

The current index event path was observed as `UNVERIFIED`.

The registry records that the engine is consumed by the current runtime but
does not grant it authoritative hard-block semantics.

Authoritative event intelligence is a later phase.

## Next step

B2 Step 2B will implement pure adapters around selected existing engine
payloads.

Adapters will:

1. receive already-produced values;
2. perform no provider calls;
3. emit `EvidenceV1` / `AnalyzerResultV1`;
4. retain raw source semantics;
5. have zero execution/risk/position/certification authority.

The live R2.2 PAPER runtime remains untouched.