"""Offline unit tests for the Dhan broker integration."""

from unittest.mock import Mock

import pytest

from services.broker.dhan_client import DhanAuthenticationError, DhanClient, DhanConfigurationError
from services.broker.dhan_market_data import DhanMarketData
from services.broker.instrument_registry import InstrumentRegistry


def test_client_uses_environment_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DHAN_CLIENT_ID", "client-id")
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "access-token")
    sdk, factory = Mock(), Mock()
    factory.return_value = sdk
    assert DhanClient(factory).sdk is sdk
    factory.assert_called_once_with("client-id", "access-token")


def test_client_rejects_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DHAN_CLIENT_ID", raising=False)
    monkeypatch.delenv("DHAN_ACCESS_TOKEN", raising=False)
    with pytest.raises(DhanConfigurationError):
        _ = DhanClient().sdk


def test_client_validates_and_rejects_mocked_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DHAN_CLIENT_ID", "client-id")
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "access-token")
    success = Mock(get_fund_limits=Mock(return_value={"status": "success"}))
    assert DhanClient(Mock(return_value=success)).validate_authentication()
    success.get_fund_limits.assert_called_once_with()
    failure = Mock(get_fund_limits=Mock(return_value={"status": "failure", "errorCode": "DH-901"}))
    with pytest.raises(DhanAuthenticationError):
        DhanClient(Mock(return_value=failure)).validate_authentication()


def test_market_data_delegates_only_read_calls() -> None:
    client = Mock()
    client.call.return_value = {"status": "success", "data": {}}
    provider = DhanMarketData(client)
    provider.get_quote("13", "idx_i")
    client.call.assert_called_with("quote_data", {"IDX_I": ["13"]})
    provider.get_historical_data("13", "IDX_I", "INDEX", "2026-01-01", "2026-01-31")
    client.call.assert_called_with("historical_daily_data", "13", "IDX_I", "INDEX", "2026-01-01", "2026-01-31", expiry_code=0, oi=False)
    provider.get_intraday_data("13", "IDX_I", "INDEX", "2026-01-01", "2026-01-01", interval=5)
    client.call.assert_called_with("intraday_minute_data", "13", "IDX_I", "INDEX", "2026-01-01", "2026-01-01", interval=5, oi=False)
    provider.get_expiry_list("13", "IDX_I")
    client.call.assert_called_with("expiry_list", "13", "IDX_I")
    provider.get_option_chain("13", "IDX_I", "2026-01-29")
    client.call.assert_called_with("option_chain", "13", "IDX_I", "2026-01-29")


def test_registry_resolves_indices_and_cached_options() -> None:
    registry = InstrumentRegistry()
    assert registry.resolve("NIFTY").security_id == "13"
    assert registry.resolve("BANKNIFTY").security_id == "25"
    assert registry.register_many([{"symbol": "NIFTY", "security_id": "99999", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX", "expiry": "2026-01-29", "strike": "25000", "option_type": "CE"}]) == 1
    assert registry.resolve_option("NIFTY", "2026-01-29", 25000, "CE").security_id == "99999"
