from datetime import (
    date,
    datetime,
    timezone,
)
from pathlib import Path

import pytest

from services.broker.provider_registry_v2 import (
    PROVIDER_REGISTRY_V2,
    assert_provider_adapter_ready,
    get_provider_registration,
    provider_adapter_ready,
)
from services.contracts.resolved_instrument_v2 import (
    ResolvedInstrumentV2,
)
from services.core.provider_routing_policy_v2 import (
    automatic_fallback_provider,
    get_planned_route,
    list_planned_routes,
    resolve_operational_primary,
)
from services.core.provider_market_adapter import (
    list_provider_market_mappings,
)


NOW = datetime(
    2026,
    9,
    16,
    10,
    0,
    tzinfo=timezone.utc,
)


def test_underlying_resolved_instrument_is_data_only_and_mapping_compatible():
    instrument = ResolvedInstrumentV2(
        resolution_id="fyers-nifty-underlying",
        provider="FYERS",
        market_symbol="NIFTY",
        market_type="INDEX",
        underlying_exchange="NSE",
        derivative_exchange="NFO",
        instrument_type="UNDERLYING",
        canonical_instrument_id=(
            "NIFTY|UNDERLYING"
        ),
        provider_symbol="NSE:NIFTY50-INDEX",
        provider_exchange="NSE",
        provider_token=None,
        contract_metadata_status=(
            "NOT_APPLICABLE"
        ),
        resolved_at=NOW,
    )

    payload = instrument.to_provider_instrument()

    assert instrument.data_only is True
    assert instrument.execution_mode == "PAPER"
    assert (
        instrument.live_execution_eligible
        is False
    )

    assert (
        payload["provider"]
        == "FYERS"
    )

    assert (
        payload["canonical_instrument_id"]
        == "NIFTY|UNDERLYING"
    )


def test_option_requires_expiry_strike_and_option_type():
    instrument = ResolvedInstrumentV2(
        resolution_id="angel-crude-option",
        provider="ANGEL_SMARTAPI",
        market_symbol="CRUDEOILM",
        market_type="COMMODITY",
        underlying_exchange="MCX",
        derivative_exchange="MCX",
        instrument_type="OPTION",
        canonical_instrument_id=(
            "CRUDEOILM|OPTION|"
            "2026-09-17|6900|CE"
        ),
        provider_symbol=(
            "CRUDEOILM17SEP266900CE"
        ),
        provider_exchange="MCX",
        provider_token="TEST",
        expiry=date(
            2026,
            9,
            17,
        ),
        strike=6900,
        option_type="CE",
        lot_size=10,
        tick_size=0.05,
        contract_metadata_status=(
            "PROVISIONAL"
        ),
        metadata_source=(
            "MCX_EXISTING_PROVISIONAL_CONTRACT"
        ),
        resolved_at=NOW,
        warnings=(
            "Metadata remains provisional.",
        ),
    )

    assert instrument.option_type == "CE"
    assert (
        instrument.contract_metadata_status
        == "PROVISIONAL"
    )


def test_unavailable_contract_metadata_cannot_smuggle_lot_or_tick_values():
    with pytest.raises(
        ValueError,
        match="cannot carry lot/tick",
    ):
        ResolvedInstrumentV2(
            resolution_id="bad",
            provider="FYERS",
            market_symbol="GOLDM",
            market_type="COMMODITY",
            underlying_exchange="MCX",
            derivative_exchange="MCX",
            instrument_type="FUTURE",
            canonical_instrument_id=(
                "GOLDM|FUTURE|TEST"
            ),
            provider_symbol="MCX:GOLDMTEST",
            provider_exchange="MCX",
            provider_token=None,
            expiry=date(
                2026,
                10,
                1,
            ),
            lot_size=100,
            tick_size=1.0,
            contract_metadata_status=(
                "UNAVAILABLE"
            ),
            resolved_at=NOW,
        )


def test_provider_registry_is_exact_data_only_and_fyers_ready():
    assert tuple(
        item.provider
        for item in PROVIDER_REGISTRY_V2
    ) == (
        "FYERS",
        "ANGEL_SMARTAPI",
    )

    fyers = get_provider_registration(
        "FYERS"
    )

    angel = get_provider_registration(
        "ANGEL_SMARTAPI"
    )

    assert fyers.role == "PRIMARY"
    assert angel.role == "SHADOW"

    assert fyers.data_only is True
    assert angel.data_only is True

    assert (
        fyers.order_capability_allowed
        is False
    )

    assert (
        angel.order_capability_allowed
        is False
    )

    assert (
        fyers.automatic_fallback_allowed
        is False
    )

    assert (
        angel.automatic_fallback_allowed
        is False
    )

    assert (
        fyers.adapter_status
        == "READY"
    )

    assert (
        angel.adapter_status
        == "PENDING_V2_ADAPTER"
    )

    assert provider_adapter_ready(
        "FYERS"
    )

    assert not provider_adapter_ready(
        "ANGEL_SMARTAPI"
    )


def test_planned_route_is_fyers_primary_and_angel_shadow_for_all_five_markets():
    markets = (
        "NIFTY",
        "SENSEX",
        "CRUDEOILM",
        "GOLDM",
        "NATGASMINI",
    )

    kinds = (
        "INSTRUMENT",
        "QUOTE",
        "DEPTH",
        "HISTORICAL",
        "STREAMING",
    )

    routes = list_planned_routes()

    assert len(routes) == 25

    for market in markets:
        for kind in kinds:
            route = get_planned_route(
                market,
                kind,
            )

            assert (
                route.primary_provider
                == "FYERS"
            )

            assert (
                route.shadow_providers
                == ("ANGEL_SMARTAPI",)
            )

            assert (
                route.routing_status
                == "PLANNED"
            )

            assert (
                route.fallback_mode
                == "FAIL_CLOSED"
            )

            assert (
                route.automatic_fallback_allowed
                is False
            )


def test_operational_route_uses_ready_fyers_primary():
    assert (
        resolve_operational_primary(
            "NIFTY",
            "QUOTE",
        )
        == "FYERS"
    )

    assert (
        assert_provider_adapter_ready(
            "FYERS"
        ).provider
        == "FYERS"
    )

    with pytest.raises(
        RuntimeError,
        match="PROVIDER_V2_ADAPTER_NOT_READY",
    ):
        assert_provider_adapter_ready(
            "ANGEL_SMARTAPI"
        )


def test_automatic_fallback_is_deliberately_absent():
    assert (
        automatic_fallback_provider(
            "NIFTY",
            "QUOTE",
        )
        is None
    )

    assert (
        automatic_fallback_provider(
            "CRUDEOILM",
            "DEPTH",
        )
        is None
    )


def test_legacy_v1_provider_mapping_remains_unchanged_and_has_no_fyers():
    providers = {
        mapping.provider
        for mapping
        in list_provider_market_mappings()
    }

    assert providers == {
        "YFINANCE",
        "ANGEL_SMARTAPI",
        "NSE_OPTION_CHAIN",
    }

    assert "FYERS" not in providers


def test_p44d_contains_no_provider_sdk_auth_or_order_authority():
    paths = (
        Path(
            "services/contracts/"
            "resolved_instrument_v2.py"
        ),
        Path(
            "services/broker/"
            "provider_registry_v2.py"
        ),
        Path(
            "services/core/"
            "provider_routing_policy_v2.py"
        ),
    )

    text = "\n".join(
        path.read_text(
            encoding="utf-8",
        )
        for path in paths
    )

    forbidden = (
        "SmartConnect",
        "fyers_apiv3",
        "generateSession",
        "access_token",
        "FYERS_SECRET_KEY",
        "ANGEL_API_KEY",
        "place_order",
        "placeOrder(",
        "submit_order",
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]
