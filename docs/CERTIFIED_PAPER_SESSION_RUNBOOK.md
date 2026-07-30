# Certified PAPER Session Runbook

## Current implementation status

Completed:

- Batch 1: fail-closed runtime safety boundary
- Batch 2: deterministic typed cycle identities and exact cycle input
- Batch 3: read-only DATA, SESSION, ANALYSIS, and OPPORTUNITY authorities
- Batch 4: concrete NIFTY/SENSEX provider readers and exact P6 bundle boundary

The executable launcher is not yet enabled.

## Batch 4 market identities

- NIFTY / NSE / token `99926000` / options exchange `NFO`
- SENSEX / BSE / token `99919000` / options exchange `BFO`

No other market identity is accepted by the certified provider reader.

## Live provider rules

The composition root injects:

- one read-only quote reader
- `LiveAnalysisPipeline`
- `LiveOptionDecisionPipeline`

The provider reader calls only `analyse()` and quote-read interfaces. It has
no broker order method, credential access, or live execution switch.

Every normalized payload states:

- `execution_mode=PAPER`
- `live_execution_eligible=False`
- `broker_order_submission=False`

## P6 boundary rules

The P6 input factory does not convert arbitrary legacy dictionaries into
certified contracts.

An injected typed builder must return an exact `CertifiedP6InputBundleV1`
containing:

- `TradePlanningPolicyV1`
- `OptionContractSelectionInputV1`
- `EntryZoneEvaluationInputV1`
- `StopLossEvaluationInputV1`
- `ThreeTargetEvaluationInputV1`
- `CapitalQuantityPlanningInputV1`

The factory then creates the exact `P6PlanningStageInputV1` using the
cycle-owned `p6_integration_id` and verifies cycle/canonical market identity.

## Remaining implementation

- typed P5 opportunity/ranking normalization builder
- new-entry P7/P8 input composition
- existing-position monitoring input composition
- journals and persistence recovery
- dashboard publication composition
- executable launcher and structured logging
- graceful shutdown certification
