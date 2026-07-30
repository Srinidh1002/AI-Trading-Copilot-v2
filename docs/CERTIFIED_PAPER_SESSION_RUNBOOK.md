# Certified PAPER Session Runbook

## Current implementation status

Completed:

- Batch 1: fail-closed runtime safety boundary
- Batch 2: deterministic typed cycle identities and exact cycle input
- Batch 3: read-only DATA, SESSION, ANALYSIS, and OPPORTUNITY adapters

The launcher does not start yet. Batch 3 deliberately uses injected read
boundaries so live provider construction remains outside the certified
authority module.

## Mandatory safety state

- `config.BROKER == "PAPER"`
- `ENABLE_PAPER_TRADING is True`
- `ENABLE_LIVE_TRADING is False`
- `execution_mode == "PAPER"`
- `live_execution_eligible is False`
- `broker_order_submission is False`
- instruments are restricted to `NIFTY` and `SENSEX`

## Batch 3 authority flow

1. DATA invokes one injected read-only market reader.
2. SESSION reuses the exact immutable session validation carried by the cycle.
3. ANALYSIS invokes one injected read-only analysis reader only when the
   session permits analysis.
4. OPPORTUNITY invokes one injected read-only evaluator and normalizes its
   result into P9 statuses:
   - `READY`
   - `NO_ACTION`
   - `BLOCKED`
   - `CONFLICTING`
   - `FAILED`

Every result explicitly carries:

- `execution_mode=PAPER`
- `live_execution_eligible=False`
- `broker_order_submission=False`

The module has no broker imports, order methods, credential access, P6
planning calls, P7 lifecycle calls, or P8 portfolio calls.

## Operating modes

### Observe-only

Analysis and existing-position monitoring may run. New PAPER entries are
disabled.

### Entry-enabled PAPER

New PAPER entries may proceed only after later batches compose certified P6,
P8, and P7 inputs. No broker order submission is permitted.

### Emergency halt

New PAPER actions are blocked. Existing-position monitoring remains enabled.

## Remaining implementation

- concrete live provider readers for NIFTY and SENSEX
- exact typed P6 planning input factory
- exact new-entry P7/P8 input factory
- existing-position monitoring input factory
- journals and persistence recovery
- dashboard publication composition
- executable launcher and structured logging
- graceful shutdown certification
