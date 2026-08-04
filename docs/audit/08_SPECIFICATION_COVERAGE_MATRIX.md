# Specification Coverage Matrix

| Specification area | Status | Evidence |
|---|---|---|
| Research/live analysis/paper modes | PARTIAL | Streamlit, live CLI, paper services exist; supported mode routing fragmented |
| Validated data and normalization | PARTIAL | live pipeline adapters; dashboard ad-hoc dict/casing |
| Multi-timeframe/technical/candle/structure/volume | PARTIAL | `LiveAnalysisPipeline` calls engines; runtime tests blocked |
| Options chain and contract selection | PARTIAL | live option pipeline has chain/selector; dashboard route differs |
| VIX and FII/DII | PARTIAL | legacy master imports engines; integration in canonical route unverified |
| Regime, alignment, contradiction | PARTIAL | regime/evidence/strategy engines exist; no unified final contract |
| Mandatory safety filters/fail-safe | CONFLICTING | live code gates; dashboard bypass; tests blocked |
| Risk/position sizing | PARTIAL | multiple risk engines/trade-plan implementation |
| One clear action/response | CONFLICTING | action/status vocabularies and response builders differ |
| Explainability/audit | PARTIAL | decision audit trail/snapshots/log UI exist; durable end-to-end proof blocked |
| Paper trading / realistic validation | PARTIAL | broad paper runtime present, but UI side effect and tests block certification |
| Controlled live execution | UNKNOWN | broker/executor code exists; no supported live order caller verified |
| Stable typed contracts / no UI logic | CONFLICTING | dataclass plus untyped snapshots; dashboard orchestration |
| No archive production dependency | CONFLICTING | verified archive imports and executable wrappers |
| Testing / safety proof | CONFLICTING | many tests exist, but current suite collection fails |
| Centralized versioned configuration | CONFLICTING | root module/package collision and scattered settings |

Status definitions: IMPLEMENTED requires verified integration; PARTIAL means relevant code exists with incomplete integration; CONFLICTING means verified code violates the baseline; UNKNOWN means audit evidence was insufficient.
