# X9-B4 — Five-market unranked provenance replay

`replay_x9_provenance_v1` requires the original exact five-market ledger,
session matrix, X8 readiness and descriptive records, eligibility and B3
comparison safeguards, plus four independently retained SHA-256 digests.
It recalculates the session matrix from original market/session evidence,
re-evaluates the five X8 candidate descriptions and rebuilds timing/safety
classifications. Mismatched digest, identity, missing market, changed session,
changed readiness or changed safeguards is rejected.

`X9ProvenanceReplayV1` retains five ordered readiness and description hashes
and reports `REPLAYED_DESCRIPTIVE` or `INCOMPLETE_DESCRIPTIVE`. These statuses
refer only to descriptive consistency: no ranks, winner, trade eligibility,
market selection, independent voting or broker authority exists. No numeric
cross-market score or economic/source-independence claim is computed.

Separately retained hashes must be persisted *outside* any artifact being
verified. Recalculation cannot prove a publisher's original figures, an
unrecorded source timestamp or an exact historical provider response. The
replay function consumes supplied immutable objects and performs no network,
filesystem, journal, session-calendar or PAPER-counter operation.
