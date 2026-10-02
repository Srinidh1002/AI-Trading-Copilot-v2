# X5-A: Offline, immutable five-market option-chain foundation

Scope: NIFTY/NFO, SENSEX/BFO, and CRUDEOILM/GOLDM/NATGASMINI on MCX; FYERS data only. No SDK, network, production runtime, Brain registry, orders, PAPER journal or certification access.

Files: `services/x5/contracts_v1.py` contains the canonical contract, individual CE/PE observation, chain capture and eligibility report; `services/x5/chain_validation_v1.py` assesses evidence quality and readiness **without calculating directional signals**.

- Requires exact canonical market, provider and option exchange; exact expiry and no duplicates of provider symbol, canonical ID, strike/side or source record.
- Separates provider observation time, retrieval time and historical replay time. A retrospectively downloaded chain is explicitly **not** point-in-time verified. `point_in_time_verified=True` is a caller assertion that also requires contemporaneous capture, provenance and timestamps; it is not cryptographic proof of provider availability.
- Rejects future-dated rows, stale records at a supplied age budget, expired contracts and index option chains on expiry day at/after 15:30 IST. MCX same-day expiry is conservatively unavailable pending exchange-specific session validation.
- Retains missing optional values as None; zero OI/volume are valid numeric observations, not substituted for missing values. Signed OI change requires a separately identified comparable baseline before it is eligible. Unverified units make affected derived features unavailable.
- Separates IV percentages from IV decimal units and refuses to mark mixed IV-unit captures ready for skew. Greeks need their own provenance; this phase does not infer theoretical Greeks.
- Whole-chain ratios/levels are unavailable if any CE/PE strike is unpaired or any contributing row lacks the relevant verified unit. The captured strike window is **not** a whole-exchange chain: a future adapter must record the strike window and coverage provenance before claiming global market totals.
- No metrics are computed here. A readiness label means only that the next *research* engine can attempt a calculation. It does not imply completeness across the exchange, trading usefulness, independent voting or execution permission.
- All X5 outputs are immutable (`frozen=True`, `slots=True`), deterministic when identical data are supplied and have zero execution, risk, position and certification authority.

**Later gates**: X5-B1 adapts existing FYERS normalized optionchain observations using validated expiry/contract identity and unit/time proofs; B2 reuses deterministic analytics without importing policy voting/selection; B3 projects correlated evidence; B4 adversarial replay; B5 frozen scoped commit. Real-provider OI/volume/IV/Greeks semantics remain UNVERIFIED until independently evidenced.
