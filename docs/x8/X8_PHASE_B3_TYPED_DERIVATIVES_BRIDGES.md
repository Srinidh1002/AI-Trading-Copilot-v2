# X8-B3 — Strict futures and volatility research bridges

New source: `services/x8/derivatives_bridge_v1.py`.

`bind_x4_futures_to_x8_v1` accepts only an exact, caller-supplied `X4ResultV1`, original session and market identity, detached result SHA-256, separately asserted availability time and explicit freshness budget. The X4 aggregate lacks independent point-in-time proof, raw-record seals and provider-specific provenance. An otherwise AVAILABLE X4 result therefore **stays UNVERIFIED**; stale/unavailable stays stale/unavailable. A future observation or release and mismatched result or identity fail closed. Genuine X4 replay/source capture authentication is a later audited seam.

`bind_x6_volatility_to_x8_v1` requires exact `X6VolatilityCaptureV1`, source `X5ChainCaptureV1`, `X6InputValidationV1`, three detached hashes and availability time. It recalculates `validate_x6_input_v1` against the original X5/X6 captures, enforces the same market/session/capture, freshness, point-in-time classification and availability. Retrospective, stale and unavailable evidence never become AVAILABLE. A caller's detached hashes and P-I-T assertions establish internal consistency, not independent provider authenticity. X5 premiums are theoretical input provenance, not executable quotes.

The resulting X8 `FUTURES` and `VOLATILITY` evidence references are descriptive. No directional regime, order choice, risk, position, broker, filesystem, provider, network or PAPER certification authority is added. The original Phase A–B2 files stay unchanged. X3 technical and X2 breadth adapters remain to be separately validated.
