# P3-5E final replay and certification

P3-5E adds optional fail-open audit hooks to deterministic position sizing,
canonical risk validation, and the canonical-risk paper-preparation branch.
The hooks use the existing `AuditEmitter` and `AuditContext` APIs, emit one
started and one terminal lifecycle event, and serialize only bounded primitive
identity, sizing, status, and count fields.

The accompanying replay scenarios are synthetic and deterministic. They cover
supported NIFTY/SENSEX BUY/CALL and SELL/PUT paths, risk gates, sizing limits,
identity preservation, and semantic comparisons that exclude generated IDs and
timestamps. They do not access providers, brokers, databases, files, analysis,
decisions, option selection, trade-plan construction, sizing during candidate
preparation, or an executor.

P3-5E does not enable paper or live execution and does not modify sizing
formulas, risk-status mapping, execution eligibility, or paper boundaries.
