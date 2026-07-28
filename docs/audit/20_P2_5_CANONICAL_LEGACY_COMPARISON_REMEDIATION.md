# P2-5 — Canonical/Legacy Diagnostic Comparison

## Scope

Added an explicit comparison layer for supplied dashboard and live-option
payloads. It adapts the supplied legacy data with the existing runtime adapter,
runs the additive canonical pipeline on the same adapted snapshot, and records
semantic differences. It is not wired into any runtime entry point.

## Implementation

- `services/canonical/comparison_models.py` defines serializable comparison and
  difference models.
- `services/canonical/comparison.py` exposes dashboard and live-option
  comparison functions, contains adaptation/pipeline errors, and compares only
  normalized contract outputs.
- `services/canonical/__init__.py` exports the explicit diagnostic APIs.
- `tests/test_canonical_comparison.py` documents side-effect-free live-option
  comparison and deterministic serialization.

## Compared semantics

Action, direction, market regime, authorization, execution state, confidence
and available scores, data health, trade-plan presence, and blockers are
compared. Expected canonical analysis-only differences are retained as facts;
the comparison layer makes no parity claim and does not select a result.

## Safety and compatibility

The module only consumes provided mappings and canonical dependencies. It does
not call the legacy dashboard, live-option pipeline, providers, brokers,
database persistence, paper execution, or live execution. Existing runtime
output, routing, thresholds, scores, confidence, and risk formulas are
unchanged.

## Verification status

Per the P2-5 workflow instruction, no pytest, coverage, lint, formatting, or
external service was run. The project owner must run focused comparison tests
and the configured suite manually.
