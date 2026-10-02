# X8 Phase A — five-market regime-evidence readiness

Frozen parent: X7 commit `b69061f562ab03b2deb3a17cd8a3943bda955cb2`, branch `x23-shadow-features-v2`. This is a **Shadow research-only** component. The canonical `services/market_regime` subsystem already exists for the historical four-index market universe. This package does not replace it, infer its MCX compatibility, or evaluate a trading regime.

`X8EvidenceReferenceV1` binds one **supplied upstream result** to its source ID, source-record ID, content hash, observation/availability instants, caller-supplied point-in-time flag and explicit status. Controlled families are TECHNICAL, BREADTH, FUTURES, OPTIONS, VOLATILITY, EXTERNAL_CONTEXT, MARKET_SESSION and DATA_QUALITY. Each family occurs at most once per market capture. Reusing the exact source-ID/record-ID pair as a second family is rejected.

`build_x8_regime_readiness_v1` requires TECHNICAL, MARKET_SESSION and DATA_QUALITY for both index markets and additionally FUTURES for the three MCX products. These are **initial research-inventory requirements**, not validated trading policy. Missing/unavailable required evidence produces UNAVAILABLE; incomplete optional supplied evidence produces PARTIAL. The output's `regime_label` is permanently UNASSESSED. Even READY means only *the listed mandatory caller-supplied references are present and self-consistent*, not that data are authentic, the market is tradable, or the regime is favorable. Dependency groups expose possible reuse; they are not empirical correlation measurements.

Hard restrictions: caller-supplied aware time; no future observation or availability; source SHA-256 length/format; statuses never auto-upgraded; fully immutable, canonical deterministic SHA-256 and zero authority. No provider, session-calendar, indicator-recalculation, trade signal, capital, broker, order, certification or persistent-state changes.

Next joint batch: adapt exact upstream X3/X4/X5/X6/X7 and existing canonical session/quality results into these references using explicit ownership and provenance. Test adapter semantics and support separately per market before any regime-classifier policy is considered.
