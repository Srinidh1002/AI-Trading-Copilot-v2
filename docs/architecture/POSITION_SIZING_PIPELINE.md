# Position-sizing pipeline

P3-5B consumes a supplied `TradePlanV1` and `RiskPolicyV1` to produce a
deterministic `PositionSizeResultV1`. It uses only configured capital, risk,
lot, and quantity limits. The service does not select contracts, rebuild plans,
prepare candidates, submit orders, or access external systems.

P3-5E adds optional `audit_emitter` and `audit_context` hooks. A validated
invocation emits one started event and exactly one terminal completed, blocked,
or failed event. Emission is fail-open and carries only bounded primitive
identity, sizing, limit, count, and status fields; it cannot affect the result.
