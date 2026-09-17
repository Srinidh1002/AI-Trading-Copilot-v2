from unittest.mock import MagicMock

import pytest

from services.options.angel_option_provider_capabilities import (
    angel_option_provider_capabilities,
)
from services.options.greeks_engine import (
    GreeksEngine,
)


def test_nifty_greeks_capability_is_supported_optional():
    result = angel_option_provider_capabilities(
        "NIFTY",
        "NFO",
    )

    assert result.option_greeks_supported is True
    assert result.option_greeks_required is False


def test_sensex_greeks_capability_is_provider_unavailable():
    result = angel_option_provider_capabilities(
        "SENSEX",
        "BFO",
    )

    assert result.option_greeks_supported is False
    assert result.option_greeks_required is False


@pytest.mark.parametrize(
    "underlying,exchange",
    (
        ("NIFTY", "BFO"),
        ("SENSEX", "NFO"),
    ),
)
def test_cross_market_capability_identity_is_rejected(
    underlying,
    exchange,
):
    with pytest.raises(ValueError):
        angel_option_provider_capabilities(
            underlying,
            exchange,
        )


def test_sensex_unsupported_greeks_short_circuits_provider_call():
    client = MagicMock()

    engine = GreeksEngine(
        client=client,
    )

    result = engine.analyze(
        "SENSEX",
        "13AUG2026",
        "BFO",
    )

    assert result["Status"] == "Unavailable"
    assert (
        result["CapabilityState"]
        == "UNSUPPORTED_BY_PROVIDER"
    )
    assert (
        result["Reason"]
        == "OPTION_GREEKS_PROVIDER_CAPABILITY_UNAVAILABLE"
    )

    client.get_option_greeks.assert_not_called()


def test_nifty_supported_greeks_calls_provider():
    client = MagicMock()

    client.get_option_greeks.return_value = {
        "data": [
            {
                "tradingSymbol": "NIFTYCE",
                "strikePrice": 25000,
                "optionType": "CE",
                "delta": 0.5,
                "gamma": 0.01,
                "theta": -10,
                "vega": 5,
                "rho": 1,
                "impliedVolatility": 12,
            }
        ]
    }

    engine = GreeksEngine(
        client=client,
    )

    result = engine.analyze(
        "NIFTY",
        "10AUG2026",
        "NFO",
    )

    assert result["Status"] == "Success"
    assert (
        result["CapabilityState"]
        == "SUPPORTED"
    )

    client.get_option_greeks.assert_called_once_with(
        "NIFTY",
        "10AUG2026",
    )


def test_supported_provider_failure_is_not_mislabeled_as_capability_absence():
    client = MagicMock()

    client.get_option_greeks.side_effect = (
        RuntimeError(
            "provider unavailable"
        )
    )

    engine = GreeksEngine(
        client=client,
    )

    result = engine.analyze(
        "NIFTY",
        "10AUG2026",
        "NFO",
    )

    assert result["Status"] == "Unavailable"
    assert (
        result["CapabilityState"]
        == "PROVIDER_FAILURE"
    )
    assert result[
        "Reason"
    ].startswith(
        "OPTION_GREEKS_PROVIDER_FAILURE:"
    )


def test_supported_empty_greeks_payload_is_data_unavailable():
    client = MagicMock()

    client.get_option_greeks.return_value = {
        "data": []
    }

    engine = GreeksEngine(
        client=client,
    )

    result = engine.analyze(
        "NIFTY",
        "10AUG2026",
        "NFO",
    )

    assert result["Status"] == "Unavailable"
    assert (
        result["CapabilityState"]
        == "SUPPORTED"
    )
    assert (
        result["Reason"]
        == "OPTION_GREEKS_DATA_UNAVAILABLE"
    )


def test_market_capabilities_are_independent():
    nifty = angel_option_provider_capabilities(
        "NIFTY",
        "NFO",
    )

    sensex = angel_option_provider_capabilities(
        "SENSEX",
        "BFO",
    )

    assert nifty.option_greeks_supported is True
    assert sensex.option_greeks_supported is False
