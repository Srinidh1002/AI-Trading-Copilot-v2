# X10-B4 — Read-only X9/X10 provenance and P7/P8 replay linkage

`replay_x10_cross_module_v1` binds the exact B4 X9 replay to the exact original
X9 ledger, B2 X10 projection and B3 reconciliation audit through their
independently supplied digests and one parent cycle. It then re-runs the B3
reconciliation using the exact caller-supplied P7/P8 source objects, source
SHA-256s and availability time. Changed source, misbound cycle, a duplicate
or unsupported position, wrong hash or changed projected result fails closed.

`INDEX_REPLAY_RECONCILED` means that the original P7/P8 **index** position
records and descriptive X9 evidence are internally consistent. It never means
that MCX positions, market-attributed pending reservations, live balances or
portfolio capital authority have been established. Unavailable inputs remain
`PARTIAL_RESEARCH_ONLY`; MCX slots always remain `MCX_UNVERIFIED`.
`deployable_capital` is permanently None and `capital_admission_allowed=False`.

X10 does not fetch repository snapshots, enumerate live positions, obtain broker
balances, reserve/release capital, advance lifecycle state, or touch PAPER
certification counters. Isolated fixture tests use explicitly marked P7/P8
test doubles. The source checks exact canonical P7/P8 types in the user's
complete repository; actual recovered-store and genuine fixture integration
must be independently tested before those capabilities can be certified. No
claim of true historical point-in-time retrieval is made.
