# P3-4C2 paper boundary

`CanonicalTradePlanResultV1` and P3-4 `TradePlanV1` inputs are accepted at the
paper boundary only as risk-pending inputs.  They are validated against the
decision and authoritative market-session validation, then rejected before
candidate sizing, executor import, broker access, or persistence.  Legacy paper
candidate preparation and execution calls remain unchanged when no P3-4 input is
provided.
