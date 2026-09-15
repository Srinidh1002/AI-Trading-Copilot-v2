from dataclasses import replace

import pytest

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.certification.task9_provider_field_capability_alignment import (
    validate_task9_provider_field_runtime_alignment,
)
from services.contracts.provider_capability_registry_v1 import (
    ProviderCapabilityRegistryV1,
    default_provider_capability_registry,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderCapability,
    Task9ProviderCapabilityReportV1,
    Task9ProviderFamily,
    Task9ProviderReadinessStatus,
)
from tests.test_task9_runtime_config_snapshot_v1 import (
    _config,
)


def _registry():
    return default_provider_capability_registry()


def _angel():
    return build_task9_angel_capability_session()


def _generic():
    return build_task9_provider_capability_report(
        _config()
    )


def _replace_generic(
    report,
    *,
    family,
    capability,
    market=None,
    exchange=None,
    **changes,
):
    rows = []

    matched = False

    for state in report.capability_states:
        if (
            state.provider_family is family
            and state.capability is capability
            and state.market == market
            and state.exchange == exchange
        ):
            rows.append(
                replace(
                    state,
                    **changes,
                )
            )
            matched = True
        else:
            rows.append(state)

    assert matched

    return Task9ProviderCapabilityReportV1(
        runtime_config_id=(
            report.runtime_config_id
        ),
        runtime_config_version=(
            report.runtime_config_version
        ),
        capability_states=tuple(rows),
    )


def _mutated_registry(
    *,
    identity,
    field,
    value,
):
    source = _registry()

    raw = {
        key: dict(fields)
        for key, fields
        in source.capabilities.items()
    }

    raw[identity][field] = value

    return ProviderCapabilityRegistryV1(
        raw
    )


def test_default_static_and_runtime_authorities_align():
    validate_task9_provider_field_runtime_alignment(
        registry=_registry(),
        angel=_angel(),
        generic=_generic(),
    )


def test_derived_oi_is_internal_proven_ready():
    report = _generic()

    row = next(
        state
        for state in report.capability_states
        if (
            state.provider_family
            is Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET
            and state.capability
            is Task9ProviderCapability.TASK9_DERIVED_OI_CHANGE
        )
    )

    assert row.required is False
    assert (
        row.live_proof_status
        is Task9LiveProofStatus.PROVEN
    )
    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.READY
    )
    assert row.startup_semantic is None


def test_native_provider_oi_change_remains_unsupported():
    report = _generic()

    row = next(
        state
        for state in report.capability_states
        if (
            state.provider_family
            is Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET
            and state.capability
            is Task9ProviderCapability.PROVIDER_NATIVE_OI_CHANGE
        )
    )

    assert row.required is False
    assert (
        row.live_proof_status
        is Task9LiveProofStatus.NOT_APPLICABLE
    )
    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.UNSUPPORTED
    )


def test_derived_oi_cannot_regress_to_pending_provider_proof():
    report = _replace_generic(
        _generic(),
        family=(
            Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET
        ),
        capability=(
            Task9ProviderCapability.TASK9_DERIVED_OI_CHANGE
        ),
        live_proof_status=(
            Task9LiveProofStatus.PENDING
        ),
        readiness_status=(
            Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_FIELD_DERIVED_OI_RUNTIME_CAPABILITY_MISMATCH"
        ),
    ):
        validate_task9_provider_field_runtime_alignment(
            registry=_registry(),
            angel=_angel(),
            generic=report,
        )


def test_provider_native_oi_cannot_be_promoted():
    report = _replace_generic(
        _generic(),
        family=(
            Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET
        ),
        capability=(
            Task9ProviderCapability.PROVIDER_NATIVE_OI_CHANGE
        ),
        live_proof_status=(
            Task9LiveProofStatus.PROVEN
        ),
        readiness_status=(
            Task9ProviderReadinessStatus.READY
        ),
        startup_semantic=None,
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_FIELD_NATIVE_OI_RUNTIME_CAPABILITY_MISMATCH"
        ),
    ):
        validate_task9_provider_field_runtime_alignment(
            registry=_registry(),
            angel=_angel(),
            generic=report,
        )


def test_static_native_oi_cannot_be_promoted():
    registry = _mutated_registry(
        identity=(
            "NIFTY",
            "NSE",
            "NFO",
        ),
        field="provider_oi_change",
        value="SUPPORTED",
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_FIELD_NATIVE_OI_STATIC_CAPABILITY_MISMATCH"
        ),
    ):
        validate_task9_provider_field_runtime_alignment(
            registry=registry,
            angel=_angel(),
            generic=_generic(),
        )


def test_spread_must_remain_derived():
    registry = _mutated_registry(
        identity=(
            "NIFTY",
            "NSE",
            "NFO",
        ),
        field="spread",
        value="SUPPORTED",
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_FIELD_SPREAD_STATIC_CAPABILITY_MISMATCH"
        ),
    ):
        validate_task9_provider_field_runtime_alignment(
            registry=registry,
            angel=_angel(),
            generic=_generic(),
        )


def test_vix_cannot_become_required():
    report = _replace_generic(
        _generic(),
        family=Task9ProviderFamily.INDIA_VIX,
        capability=Task9ProviderCapability.INDIA_VIX,
        required=True,
    )

    with pytest.raises(
        ValueError,
        match="TASK9_FIELD_VIX_MUST_REMAIN_OPTIONAL",
    ):
        validate_task9_provider_field_runtime_alignment(
            registry=_registry(),
            angel=_angel(),
            generic=report,
        )


def test_bfo_greeks_static_capability_cannot_be_promoted():
    registry = _mutated_registry(
        identity=(
            "SENSEX",
            "BSE",
            "BFO",
        ),
        field="greeks",
        value="SUPPORTED",
    )

    with pytest.raises(
        ValueError,
        match="TASK9_FIELD_BFO_GREEKS_ALIGNMENT_MISMATCH",
    ):
        validate_task9_provider_field_runtime_alignment(
            registry=registry,
            angel=_angel(),
            generic=_generic(),
        )


@pytest.mark.parametrize(
    "field",
    (
        "5m_candles",
        "15m_candles",
        "1h_candles",
        "1d_candles",
    ),
)
def test_candle_fields_cannot_be_prematurely_promoted(
    field,
):
    registry = _mutated_registry(
        identity=(
            "NIFTY",
            "NSE",
            "NFO",
        ),
        field=field,
        value="SUPPORTED",
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_FIELD_CANDLE_CAPABILITY_PREMATURE_PROMOTION"
        ),
    ):
        validate_task9_provider_field_runtime_alignment(
            registry=registry,
            angel=_angel(),
            generic=_generic(),
        )


def test_wrong_types_fail_closed():
    with pytest.raises(TypeError):
        validate_task9_provider_field_runtime_alignment(
            registry=object(),
            angel=_angel(),
            generic=_generic(),
        )

    with pytest.raises(TypeError):
        validate_task9_provider_field_runtime_alignment(
            registry=_registry(),
            angel=object(),
            generic=_generic(),
        )

    with pytest.raises(TypeError):
        validate_task9_provider_field_runtime_alignment(
            registry=_registry(),
            angel=_angel(),
            generic=object(),
        )
