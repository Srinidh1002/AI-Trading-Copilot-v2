# Certified PAPER Session Runbook

## Current status

The certified P9 orchestration engine and P10 publication path exist. The
production composition root is being added in staged batches.

Completed:

- Batch 1: fail-closed runtime safety boundary
- Batch 2: deterministic typed cycle identities and exact
  `PaperOrchestrationCycleInputV1` construction

The launcher does not start yet. Live-read authorities and typed P6/P7/P8
adapters remain to be composed.

## Mandatory safety state

- `config.BROKER == "PAPER"`
- `ENABLE_PAPER_TRADING is True`
- `ENABLE_LIVE_TRADING is False`
- `execution_mode == "PAPER"`
- `live_execution_eligible is False`
- `broker_order_submission is False`
- supported instruments are restricted to `NIFTY` and `SENSEX`

## Cycle identity rules

Certified opportunity and monitoring cycles use separate deterministic
identity namespaces.

Identity inputs are:

- cycle kind
- observation ID
- underlying symbol
- exchange
- trading day
- exact market timestamp

The factory generates independent identities for:

- P9 cycle and idempotency key
- P6 integration
- P8 admission request, idempotency, and event
- P7 transition, position, and entry fill
- P8 update idempotency and event

The factory never uses `object.__new__`, random fixture identities, broker
order methods, credentials, or legacy trading engines.

## Operating modes

### Observe-only

Analysis and existing-position monitoring may run. New PAPER entries are
disabled.

### Entry-enabled PAPER

New PAPER entries may proceed only through certified P6, P8, and P7 decisions.
This mode still has no broker order submission.

### Emergency halt

New PAPER actions are blocked. Existing-position monitoring remains enabled.

## Credential handling

The runtime may validate that required Angel One credential variables are
present. It must never print their values.

## Remaining implementation

- live-read observation and analysis authority adapters
- exact typed P6 planning input factory
- exact new-entry P7/P8 input factory
- existing-position monitoring input factory
- journals and persistence recovery
- dashboard publication composition
- executable launcher
- structured cycle logging
- graceful shutdown certification
