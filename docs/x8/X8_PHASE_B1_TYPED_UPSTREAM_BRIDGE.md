# X8-B1 — Typed, source-bound upstream evidence bridges

Frozen parent: X7 at `b69061f562ab03b2deb3a17cd8a3943bda955cb2`. All development remains isolated in the Brain worktree. The X8-A contracts and X8 readiness builder are unchanged.

`bind_x5_options_to_x8_v1` accepts only the immutable original `X5ChainCaptureV1` and `X5ChainValidationV1`, requires detached SHA-256 anchors for both, recomputes the canonical X5 validation from the original capture with an explicit `max_age_seconds`, and binds market/session/capture/source timestamps exactly. It emits a single `OPTIONS`-family `X8EvidenceReferenceV1`. Recomputed X5 validation and hash binding are internal consistency checks, **not independent evidence that the FYERS upstream records are authentic**.

`bind_x7_context_to_x8_v1` accepts only an immutable `X7ResearchViewV1` and a separately supplied expected full-view SHA-256. It checks the market/session/capture, exact validation-to-capture digest and supplied result-availability instant. It preserves the X7 view's AVAILABLE/PARTIAL/UNAVAILABLE classification. In the current X7 design, MCX does not acquire index-only institutional evidence and typically remains PARTIAL even if the global and calendar sources were available.

Both bridges require caller-supplied awareness of when the *result itself* became available. A result whose supplied availability instant is later than the consuming X8 `as_of` is rejected. `point_in_time_verified` is never promoted from a retrospective original. Without adequate original flags and a result-availability instant, the projected reference is UNVERIFIED, not AVAILABLE. Unavailable upstream remains unavailable.

**Not built in B1:** an automatic source adapter for X2/X3/X4/X6, quality or session-calendar readers, actual network ingestion, empirical regime computation, independent source authentication, a directional vote, trade execution, risk/position authority or PAPER certification. Those interfaces require their own typed ownership and tests before any X8 classification policy. The upstream bridges do not modify frozen X5/X7 files.
