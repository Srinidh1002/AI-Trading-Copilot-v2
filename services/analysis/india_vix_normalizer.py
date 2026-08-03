"""Provider-free adapter from IndiaVixCaptureResultV1 to canonical VIX snapshots."""
from __future__ import annotations

from services.contracts.india_vix_capture_result_v1 import IndiaVixCaptureResultV1
from services.contracts.india_vix_regime_policy_v1 import DEFAULT_INDIA_VIX_REGIME_POLICY, IndiaVixRegimePolicyV1, classify_india_vix_regime
from services.contracts.volatility_snapshot_v1 import VolatilitySnapshotV1


def normalize_india_vix_capture(
    capture: IndiaVixCaptureResultV1,
    policy: IndiaVixRegimePolicyV1 = DEFAULT_INDIA_VIX_REGIME_POLICY,
) -> tuple[VolatilitySnapshotV1 | None, VolatilitySnapshotV1 | None]:
    """Use capture evidence unchanged; never call a provider or invent VIX data."""
    if type(capture) is not IndiaVixCaptureResultV1:
        raise TypeError("capture must be exact IndiaVixCaptureResultV1")
    if type(policy) is not IndiaVixRegimePolicyV1:
        raise TypeError("policy must be exact IndiaVixRegimePolicyV1")
    # A VolatilitySnapshot requires a source timestamp.  Without an actual
    # provider timestamp the honest canonical representation is no snapshot.
    if capture.provider_timestamp is None:
        return (None, None)
    regime = classify_india_vix_regime(capture.current_value, policy)
    available = capture.source_status == "READY" and regime != "UNAVAILABLE"
    snapshots: list[VolatilitySnapshotV1] = []
    for symbol, exchange in (("NIFTY", "NSE"), ("SENSEX", "BSE")):
        snapshots.append(VolatilitySnapshotV1(
            volatility_snapshot_id=f"{capture.capture_id}:{symbol}", created_at=capture.evaluated_at,
            underlying_symbol=symbol, exchange=exchange, volatility_symbol="INDIA_VIX", volatility_exchange="NSE",
            source_id=capture.provider, source_timestamp=capture.provider_timestamp,
            volatility_value=capture.current_value if available else None,
            previous_volatility_value=capture.previous_close if available else None,
            volatility_change_percent=None, normalized_volatility_regime=regime if available else "UNAVAILABLE",
            is_partial=not available, blockers=capture.blockers if not available else (), warnings=capture.warnings,
            metadata={"capture_id": capture.capture_id, "provider_token": capture.provider_token} if available else {"capture_id": capture.capture_id},
        ))
    return (snapshots[0], snapshots[1])
