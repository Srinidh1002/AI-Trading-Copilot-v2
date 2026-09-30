# B2 Source Adapters V1

## Purpose

Source Adapters V1 translate already-produced values from the current
production analyzer families into the common Brain evidence contract.

Adapters do not fetch data and do not make trading decisions.

## Current scope

### Index premarket adapter

Translates already-produced:

- previous-session OHLC;
- gap evidence;
- global-risk evidence;
- India VIX;
- FII/DII institutional flow;
- legacy event-calendar state.

### Index news adapter

Preserves:

- source sentiment;
- source directional interpretation;
- bullish/bearish/headline counts;
- feed coverage;
- degraded/unavailable status.

### Index technical adapter

Translates the existing legacy index technical path.

It can preserve:

- MTF direction;
- RSI;
- ADX;
- optional EMA state;
- optional MACD state;
- optional Bollinger state;
- regime.

Optional technical values are omitted when the current source did not emit
them. The adapter does not fabricate them from the canonical technical
package.

### MCX native adapter

Translates already-produced:

- MTF;
- regime;
- structure/VWAP relation;
- futures Price/OI state;
- raw PCR;
- stable PCR;
- max pain.

## PCR rule

The adapter does not normalize PCR semantics.

The raw value, stable value, original directional interpretation and an
explicit source-interpretation label are retained.

This is required because B1 found index and MCX PCR semantics are not yet safe
to treat as interchangeable.

## Event rule

`UNVERIFIED` remains `UNVERIFIED`.

A legacy event source that is not authoritative does not become authoritative
because it passed through a Brain adapter.

## Authority boundary

Adapters have no authority to:

- issue BUY_CALL / BUY_PUT;
- submit orders;
- change capital or risk;
- override data-quality gates;
- manage positions;
- increment certification;
- promote policies;
- start or stop workers.

They emit `AnalyzerResultV1`, whose execution authority is permanently false.

## Runtime boundary

B2 Source Adapters V1 are not imported by the live NIFTY, SENSEX, MCX or
supervisor entrypoints.

A later shadow/snapshot phase may call the adapters in an isolated observation
path. That future wiring requires a separate reviewed change.

## Next step

After these adapters are frozen, B2 will close remaining adapter coverage and
define the market/analyzer registry interface used to build deterministic
MarketSnapshot records in B3.