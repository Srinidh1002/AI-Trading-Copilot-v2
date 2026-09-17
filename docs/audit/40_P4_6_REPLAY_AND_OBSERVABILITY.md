# P4-6 replay and observability audit

Created immutable observation and replay-result contracts, a locked in-memory
observation repository, explicit observation builder, and read-only replay
service. Exports were added only through contracts and paper package surfaces.

Stages: RISK, CANDIDATE, REQUEST, AUTHORIZATION, EXECUTION, ORDER_STATE,
PIPELINE_RESULT. Replay statuses: MATCHED, MISMATCHED, INCOMPLETE,
NOT_REPLAYABLE, FAILED. Replay semantically compares canonical linkage,
identity, long-premium direction, quantities, statuses, and fill evidence.
The repository is process-local, tuple-snapshot based, deterministically
ordered, duplicate-safe, and `RLock` protected.

The only defect corrected was reconstruction of a serialised timestamp in a
new mismatch test; runtime behavior was unaffected. No automatic storage,
execution, authorization, persistence, or live behavior was introduced.

Certification outputs: observation contract `63 passed in 0.64s`; replay
contract `48 passed in 0.60s`; repository `72 passed in 0.66s`; builder `71
passed in 0.67s`; replay `91 passed in 0.67s`; isolation `40 passed in 0.68s`;
four-index `40 passed in 0.65s`; combined `425 passed in 1.14s`; P4-5
regression `326 passed in 1.01s`; P4-4 `170 passed in 0.78s`; P4 `660 passed
in 1.58s`; canonical `275 passed in 1.22s`; safety `284 passed, 2 warnings in
1.88s`; import `P4-6 imports passed`; full suite `5527 passed, 2 warnings in
16.84s`. The two warnings are pre-existing SmartAPI TLS deprecations. P4-6 is
certified.
