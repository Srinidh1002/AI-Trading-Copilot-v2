# X10-B3 — Detached, read-only P7/P8 projection replay

New source: `services/x10/reconciliation_audit_v1.py`.

`audit_x10_reconciliation_v1` requires the exact X9 ledger, exact X10-B2 typed projection, separately anchored projection digest and the original caller-supplied P7/P8 snapshot objects and detached source hashes. It reruns the original B2 typed projection and requires identical output, refusing changed ids, timestamps, hash anchors, inventory, lifecycle states or sequence. In the complete repository, B2's original adapter imports the exact P7/P8 canonical persistence classes. This phase still never accesses persistence services or production repositories directly.

The report distinguishes unavailable P8, P8-only/unreconciled and matched supplied P7/P8 records. Matched supplied records **do not** prove discovery of every position held in an external store. Pending reservation counts with missing market attribution remain shared, not split between NIFTY and SENSEX. MCX account state remains `MCX_UNVERIFIED`; the report cannot infer deployable capital, approve admission, move reservations, place orders or affect PAPER trade counts.

The isolated B3 X10 tests use explicit fake P7/P8 contract shapes. Genuine canonical-type replay and recovery testing must be performed using the full user worktree before stronger claims. Do not commit B3 until the combined X8–X10 B5 audit/freeze.
