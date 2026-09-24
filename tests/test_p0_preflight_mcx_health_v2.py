"""Part 6 — preflight provider health for MCX markets. Mocks only."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from tools import preflight_and_start_five_market_paper as pf


@pytest.fixture
def creds():
    return SimpleNamespace(app_id="APP", access_token="TOKEN")


def test_index_only_still_works(creds, monkeypatch):
    class _H:
        ok = True
        symbol = "NSE:NIFTY50-INDEX"
        reason_code = "OK"
    monkeypatch.setattr(
        "services.broker.fyers_provider_runtime_v2.check_fyers_provider_health_v2",
        lambda client, symbol: SimpleNamespace(
            ok=True, symbol=symbol, reason_code="OK",
        ),
    )
    monkeypatch.setattr(
        "services.broker.fyers_sdk_data_client_v2.build_fyers_data_client_v2",
        lambda **kw: SimpleNamespace(
            data_only=True,
            order_capability_allowed=False,
            automatic_fallback_allowed=False,
        ),
    )
    out = pf.check_provider_health(creds, ("NIFTY", "SENSEX"))
    assert out["NIFTY"][0] is True
    assert "OK" in out["NIFTY"][1]
    assert out["SENSEX"][0] is True


def test_mcx_identity_ok_and_quote_rows(creds, monkeypatch):
    fake_runtime = SimpleNamespace(
        data_only=True,
        order_capability_allowed=False,
        automatic_fallback_allowed=False,
        identity=SimpleNamespace(
            resolve_active=lambda product: {
                "status": "OK",
                "futures": {"token": "TOK1", "symbol": "CRUDEOILM_FUT"},
            },
        ),
        data=SimpleNamespace(
            getMarketData=lambda mode, payload: {"data": {"fetched": [{"row": 1}]}},
        ),
    )
    monkeypatch.setattr(
        "mcx.mcx_fyers_runtime_v2.build_mcx_fyers_runtime_from_env_v2",
        lambda **kw: fake_runtime,
    )
    out = pf.check_provider_health(creds, ("CRUDEOILM",))
    assert out["CRUDEOILM"][0] is True
    assert "OK" in out["CRUDEOILM"][1]


def test_mcx_identity_not_ok_is_hold(creds, monkeypatch):
    fake_runtime = SimpleNamespace(
        data_only=True,
        order_capability_allowed=False,
        automatic_fallback_allowed=False,
        identity=SimpleNamespace(
            resolve_active=lambda product: {
                "status": "EVIDENCE_UNAVAILABLE_IDENTITY",
                "reason": "NO_NON_EXPIRED_OPTION_EVIDENCE",
                "futures": None,
            },
        ),
        data=SimpleNamespace(getMarketData=lambda mode, payload: {"data": {"fetched": []}}),
    )
    monkeypatch.setattr(
        "mcx.mcx_fyers_runtime_v2.build_mcx_fyers_runtime_from_env_v2",
        lambda **kw: fake_runtime,
    )
    out = pf.check_provider_health(creds, ("CRUDEOILM",))
    assert out["CRUDEOILM"][0] is False
    assert "MCX_IDENTITY" in out["CRUDEOILM"][1]


def test_mcx_empty_quote_rows_is_hold(creds, monkeypatch):
    fake_runtime = SimpleNamespace(
        data_only=True,
        order_capability_allowed=False,
        automatic_fallback_allowed=False,
        identity=SimpleNamespace(
            resolve_active=lambda product: {
                "status": "OK",
                "futures": {"token": "TOK1"},
            },
        ),
        data=SimpleNamespace(getMarketData=lambda mode, payload: {"data": {"fetched": []}}),
    )
    monkeypatch.setattr(
        "mcx.mcx_fyers_runtime_v2.build_mcx_fyers_runtime_from_env_v2",
        lambda **kw: fake_runtime,
    )
    out = pf.check_provider_health(creds, ("CRUDEOILM",))
    assert out["CRUDEOILM"][0] is False
    assert "NO_QUOTE_ROWS" in out["CRUDEOILM"][1]


def test_mcx_runtime_build_failure_holds_all(creds, monkeypatch):
    def _boom(**kw):
        raise RuntimeError("sdk init failed")
    monkeypatch.setattr(
        "mcx.mcx_fyers_runtime_v2.build_mcx_fyers_runtime_from_env_v2",
        _boom,
    )
    out = pf.check_provider_health(creds, ("CRUDEOILM", "GOLDM", "NATGASMINI"))
    for m in ("CRUDEOILM", "GOLDM", "NATGASMINI"):
        assert out[m][0] is False
        assert "MCX_PROVIDER_SETUP_FAILED" in out[m][1]


def test_mcx_missing_future_token_is_hold(creds, monkeypatch):
    fake_runtime = SimpleNamespace(
        data_only=True,
        order_capability_allowed=False,
        automatic_fallback_allowed=False,
        identity=SimpleNamespace(
            resolve_active=lambda product: {"status": "OK", "futures": {"symbol": "X"}},
        ),
        data=SimpleNamespace(getMarketData=lambda mode, payload: {"data": {"fetched": []}}),
    )
    monkeypatch.setattr(
        "mcx.mcx_fyers_runtime_v2.build_mcx_fyers_runtime_from_env_v2",
        lambda **kw: fake_runtime,
    )
    out = pf.check_provider_health(creds, ("CRUDEOILM",))
    assert out["CRUDEOILM"][0] is False
    assert "FUTURE_TOKEN_MISSING" in out["CRUDEOILM"][1]


def test_mixed_index_and_mcx(creds, monkeypatch):
    monkeypatch.setattr(
        "services.broker.fyers_provider_runtime_v2.check_fyers_provider_health_v2",
        lambda client, symbol: SimpleNamespace(ok=True, symbol=symbol, reason_code="OK"),
    )
    monkeypatch.setattr(
        "services.broker.fyers_sdk_data_client_v2.build_fyers_data_client_v2",
        lambda **kw: SimpleNamespace(
            data_only=True,
            order_capability_allowed=False,
            automatic_fallback_allowed=False,
        ),
    )
    fake_runtime = SimpleNamespace(
        data_only=True,
        order_capability_allowed=False,
        automatic_fallback_allowed=False,
        identity=SimpleNamespace(
            resolve_active=lambda product: {
                "status": "OK",
                "futures": {"token": "TOK"},
            },
        ),
        data=SimpleNamespace(
            getMarketData=lambda mode, payload: {"data": {"fetched": [{"x": 1}]}},
        ),
    )
    monkeypatch.setattr(
        "mcx.mcx_fyers_runtime_v2.build_mcx_fyers_runtime_from_env_v2",
        lambda **kw: fake_runtime,
    )
    out = pf.check_provider_health(creds, ("NIFTY", "CRUDEOILM"))
    assert out["NIFTY"][0] is True
    assert out["CRUDEOILM"][0] is True
