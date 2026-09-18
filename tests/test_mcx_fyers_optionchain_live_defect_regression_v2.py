from __future__ import annotations

import ast
from pathlib import Path

import pytest

import services.options.fyers_option_chain_provider_v2 as provider_module
from services.broker.fyers_response_normalizer_v2 import (
    FyersResponseNormalizationError,
)
from services.options.fyers_option_chain_provider_v2 import (
    FyersOptionChainProviderV2,
)

ROOT = Path(__file__).resolve().parents[1]


class _FakeOptionChainClient:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def optionchain(self, data=None):
        self.requests.append(dict(data or {}))
        return self.response


def _ok_response(expiry_data):
    return {
        "s": "ok",
        "code": 200,
        "message": "",
        "data": {
            "expiryData": expiry_data,
            "optionsChain": [],
            "callOi": 1,
            "putOi": 1,
        },
    }


def test_provider_uses_fyers_expirydata_without_local_timestamp(
    monkeypatch,
):
    client = _FakeOptionChainClient(
        _ok_response(
            [
                {
                    "date": "15-10-2026",
                    "expiry": 1792087200,
                    "expiry_flag": "M",
                },
                {
                    "date": "17-11-2026",
                    "expiry": 1794938400,
                    "expiry_flag": "M",
                },
            ]
        )
    )

    monkeypatch.setattr(
        provider_module,
        "normalize_option_chain",
        lambda response: [],
    )

    provider = FyersOptionChainProviderV2(client)

    result = provider.get_option_chain(
        underlying_symbol=("MCX:CRUDEOILM26OCTFUT"),
        strike_count=10,
        expected_expiry="2026-10-15",
    )

    assert client.requests == [
        {
            "symbol": "MCX:CRUDEOILM26OCTFUT",
            "strikecount": 10,
        }
    ]

    assert result["provider_expiry_date"] == "2026-10-15"

    assert result["provider_expiry_timestamp"] == 1792087200

    assert result["request_count"] == 1

    assert result["per_contract_depth_requests"] == 0


def test_provider_fails_closed_when_expected_expiry_missing(
    monkeypatch,
):
    client = _FakeOptionChainClient(
        _ok_response(
            [
                {
                    "date": "17-11-2026",
                    "expiry": 1794938400,
                }
            ]
        )
    )

    monkeypatch.setattr(
        provider_module,
        "normalize_option_chain",
        lambda response: [],
    )

    provider = FyersOptionChainProviderV2(client)

    with pytest.raises(
        FyersResponseNormalizationError,
        match="expected option expiry",
    ):
        provider.get_option_chain(
            underlying_symbol=("MCX:CRUDEOILM26OCTFUT"),
            strike_count=10,
            expected_expiry="2026-10-15",
        )

    assert len(client.requests) == 1


def test_native_chain_removed_two_live_defect_assumptions():
    path = ROOT / "src" / "mcx" / "mcx_fyers_native_chain_v2.py"

    source = path.read_text(encoding="utf-8")

    tree = ast.parse(source)

    function_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(
            node,
            ast.FunctionDef,
        )
    }

    assert "_expiry_timestamp" not in function_names
    assert 'f"MCX:{product}"' not in source

    optionchain_calls = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if isinstance(func, ast.Attribute) and func.attr == "get_option_chain":
            optionchain_calls.append(node)

    assert len(optionchain_calls) == 1

    keyword_names = {keyword.arg for keyword in optionchain_calls[0].keywords}

    assert "expected_expiry" in keyword_names
    assert "expiry_timestamp" not in keyword_names


def test_bridge_resolves_future_after_selected_option_expiry():
    path = ROOT / "src" / "mcx" / "mcx_fyers_bridge_v2.py"

    source = path.read_text(encoding="utf-8")

    tree = ast.parse(source)

    comparisons = {
        ast.unparse(node) for node in ast.walk(tree) if isinstance(node, ast.Compare)
    }

    assert "record.expiry > nearest_expiry" in comparisons

    matching_future_resolution = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if not (isinstance(func, ast.Attribute) and func.attr == "resolve"):
            continue

        keywords = {
            keyword.arg: keyword.value
            for keyword in node.keywords
            if keyword.arg is not None
        }

        instrument = keywords.get("instrument_type")

        expiry = keywords.get("expiry")

        if not (
            isinstance(
                instrument,
                ast.Constant,
            )
            and instrument.value == "FUTURE"
        ):
            continue

        if isinstance(expiry, ast.Name) and expiry.id == "option_future_expiry":
            matching_future_resolution = True

    assert matching_future_resolution
