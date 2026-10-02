# X6-B4 — Adversarial replay and provenance hardening (offline Shadow)

## Scope and immutable authority

The `services.x6.replay_provenance_v1` module audits immutable X5 and X6 captures. It never performs provider I/O, selects a contract, places/modifies/cancels orders, publishes an independent Brain vote, controls risk/positions, or increments PAPER certification. Every versioned contract is frozen, data-only, `independent_vote=False`, and has all execution/risk/position/certification/live eligibility flags disabled. A successful offline replay is **not** proof of live FYERS provenance, accuracy, historical availability, options-model suitability, profitability, or PAPER readiness.

## Inputs and retained witnesses

A replay frame carries an X5 chain capture, an X6 input capture, recalculated input validation, X6-B2 IV/Greeks, X6-B3 volatility-regime result, optional frozen X6-B3 historical summary points, and optionally X6-B1 reference pricing with its **exact, explicit** volatility-input configuration. It stores SHA-256 witnesses for source captures, validation, B1/B2/B3 results, every X5/X6 source row and every history point. The optional B1 path is **not** audited when no B1 object/input pair was captured; absence must not be reported as a pass.

`seal_x6_replay_frame_v1` derives these witnesses from supplied in-memory inputs. Keep witness digests **independently**, outside mutable capture storage. Re-sealing tampered data simply hashes the tampered data; matching self-generated hashes neither authenticates FYERS nor demonstrates contemporaneous availability. The historical point summary hash cannot independently verify the original historical source capture unless that source and its separately retained witness are also preserved and audited.

`replay_x6_history_v1` verifies original witnesses, recomputes each stored B1 (when supplied), B2, B3 and X6 input-validation result, and requires exact hashes. It requires a bounded, immutable, chronological sequence for **one** of the five markets, distinct capture/source-row IDs and consistent session identity per IST calendar day. It rejects same-expiry option-ID drift, futures identity changes and expiry-instant changes; advancing to a later option expiry is allowed and explicitly recorded.

The resulting records have a deterministic SHA-256 chain and optional externally retained final digest. They report `FIRST_FRAME`, `SAME_WINDOW`, `WINDOW_CHANGED` or `EXPIRY_CHANGED` transitions, model-assumption changes, statuses, original source hashes and `CLAIMED_POINT_IN_TIME` versus `RETROSPECTIVE_UNPROVEN`. A claimed PIT flag merely reflects the externally supplied verification flags, **not** independent market-data publication proof. Changes in the capture window and expiry never authorize cross-frame metric comparisons: `cross_frame_metric_comparison_allowed=False` for every record and result. The only historical comparisons available are those separately permitted by the strictly comparable X6-B3 point-in-time, same-expiry, same-ATM-strike history gates.

A passed replay establishes internal consistency **relative to the independently retained witnesses** and the deterministic implementation. It does not establish that a backfilled quote existed at its simulated as-of time, that option contract expiries, rate/yield conventions or provider field units have been independently verified, or that Greeks are exchange-provided.

## Verification and freeze prerequisites

Run the five X6 test files, all combined Brain/X1–X6 tests, and the existing five selected FYERS provider tests plus X5/X6. Verify formatting/lint locally using Ruff (not available in the offline build). Complete the final scoped B5 file/authority audit before staging X6. Stage X6 sources, `tests/test_x6_*.py`, and `docs/x6/*.md` by exact file names only. Preserve the frozen X1–X5 commit, untracked audit evidence, `.venv312` and separate production PAPER worktree. Never treat the Shadow research suite as an execution or certification gate.
