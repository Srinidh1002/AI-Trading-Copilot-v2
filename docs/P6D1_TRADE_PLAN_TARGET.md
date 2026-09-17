# P6D-1 Trade-plan target contract
## Purpose
Immutable intent for exactly one future plan target.
## Architectural boundary
No market data, policy evaluation, provider, broker, order, or execution dependency.
## Fields
Number, premium price, allocation fraction, reward per unit, RR, role, and schema version.
## Target numbering and roles
1/RISK_REDUCTION, 2/PRIMARY, and 3/EXTENDED are exact pairs.
## Units
Target price and reward are INR option premium per unit; allocation uses 0–1.
## Validation
All numeric values are finite positive scalars; allocation is at most one.
## Serialization and immutability
Frozen deterministic dictionaries and JSON; semantic form includes every field.
## PAPER-planning boundary
No target is calculated, no quantity allocation occurs, and no order/execution occurs.
## P6D-2 handoff
The parent plan will order exactly three validated child targets.
