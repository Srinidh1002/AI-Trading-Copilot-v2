# Certified PAPER Session Runbook

## Current status

The certified P9 orchestration engine and P10 publication path exist, but the
production composition root is being added in staged batches.

Batch 1 establishes fail-closed runtime safety only. It does not yet start the
live-read orchestration loop.

## Mandatory safety state

- `config.BROKER == "PAPER"`
- `ENABLE_PAPER_TRADING is True`
- `ENABLE_LIVE_TRADING is False`
- `execution_mode == "PAPER"`
- `live_execution_eligible is False`
- `broker_order_submission is False`
- supported instruments are restricted to `NIFTY` and `SENSEX`

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

- live typed cycle-input factory
- opportunity authority composition
- existing-position monitoring composition
- journals and persistence recovery
- dashboard publication composition
- executable launcher
- structured cycle logging
- graceful shutdown certification
