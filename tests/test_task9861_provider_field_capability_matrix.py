import pytest

from services.contracts.provider_capability_registry_v1 import (
    FIELDS,
    IDENTITIES,
    STATES,
    ProviderCapabilityRegistryV1,
    default_provider_capability_registry,
)


NIFTY = (
    "NIFTY",
    "NSE",
    "NFO",
)

SENSEX = (
    "SENSEX",
    "BSE",
    "BFO",
)


def _state(
    identity,
    field,
):
    return (
        default_provider_capability_registry()
        .state(
            *identity,
            field,
        )
    )


def test_registry_has_exact_two_market_identities():
    assert IDENTITIES == frozenset(
        {
            NIFTY,
            SENSEX,
        }
    )


def test_registry_has_exact_field_contract():
    assert FIELDS == (
        "spot",
        "provider_timestamp",
        "5m_candles",
        "15m_candles",
        "1h_candles",
        "1d_candles",
        "option_universe",
        "premium_ltp",
        "oi",
        "provider_oi_change",
        "derived_oi_change",
        "volume",
        "bid",
        "ask",
        "spread",
        "iv",
        "greeks",
        "india_vix_applicability",
    )


def test_required_is_not_a_field_state():
    assert "REQUIRED" not in STATES


@pytest.mark.parametrize(
    "identity",
    (
        NIFTY,
        SENSEX,
    ),
)
@pytest.mark.parametrize(
    "field",
    (
        "spot",
        "provider_timestamp",
        "option_universe",
        "premium_ltp",
        "oi",
        "volume",
        "bid",
        "ask",
    ),
)
def test_common_provider_fields_are_supported(
    identity,
    field,
):
    assert (
        _state(
            identity,
            field,
        )
        == "SUPPORTED"
    )


@pytest.mark.parametrize(
    "identity",
    (
        NIFTY,
        SENSEX,
    ),
)
def test_provider_oi_change_is_not_certified_authority(
    identity,
):
    assert (
        _state(
            identity,
            "provider_oi_change",
        )
        == "UNSUPPORTED"
    )


@pytest.mark.parametrize(
    "identity",
    (
        NIFTY,
        SENSEX,
    ),
)
def test_same_session_oi_change_is_derived(
    identity,
):
    assert (
        _state(
            identity,
            "derived_oi_change",
        )
        == "DERIVED"
    )


@pytest.mark.parametrize(
    "identity",
    (
        NIFTY,
        SENSEX,
    ),
)
def test_spread_is_derived_from_bid_ask(
    identity,
):
    assert (
        _state(
            identity,
            "spread",
        )
        == "DERIVED"
    )


@pytest.mark.parametrize(
    "identity",
    (
        NIFTY,
        SENSEX,
    ),
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
def test_direct_candle_live_capability_remains_unverified(
    identity,
    field,
):
    assert (
        _state(
            identity,
            field,
        )
        == "UNVERIFIED_LIVE"
    )


def test_nifty_iv_is_supported():
    assert (
        _state(
            NIFTY,
            "iv",
        )
        == "SUPPORTED"
    )


def test_nifty_greeks_are_supported():
    assert (
        _state(
            NIFTY,
            "greeks",
        )
        == "SUPPORTED"
    )


def test_sensex_iv_is_unsupported():
    assert (
        _state(
            SENSEX,
            "iv",
        )
        == "UNSUPPORTED"
    )


def test_sensex_greeks_are_unsupported():
    assert (
        _state(
            SENSEX,
            "greeks",
        )
        == "UNSUPPORTED"
    )


@pytest.mark.parametrize(
    "identity",
    (
        NIFTY,
        SENSEX,
    ),
)
def test_india_vix_is_optional_context(
    identity,
):
    assert (
        _state(
            identity,
            "india_vix_applicability",
        )
        == "OPTIONAL"
    )


def test_registry_is_immutable():
    registry = (
        default_provider_capability_registry()
    )

    with pytest.raises(TypeError):
        registry.capabilities[
            NIFTY
        ][
            "spot"
        ] = "UNSUPPORTED"


def test_invalid_state_is_rejected():
    registry = (
        default_provider_capability_registry()
    )

    raw = {
        identity: dict(fields)
        for identity, fields
        in registry.capabilities.items()
    }

    raw[NIFTY]["spot"] = "REQUIRED"

    with pytest.raises(
        ValueError,
        match="invalid provider capability registry",
    ):
        ProviderCapabilityRegistryV1(
            raw
        )
