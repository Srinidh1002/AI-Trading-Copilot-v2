# CanonicalTradePlanResultV1

The optional P3-4 canonical trade-plan wrapper may emit fail-open audit events
for selection and plan construction. Events contain only bounded identifiers and
scalar contract-selection fields; they do not serialize snapshots, decisions,
option universes, or option chains.
