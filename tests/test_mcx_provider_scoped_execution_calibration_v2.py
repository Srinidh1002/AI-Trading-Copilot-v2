"""FYERS provider-scoped execution-calibration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcx import mcx_exec_config as cfg
from mcx.mcx_exec_quote import (
    make_execution_quote,
    validate_quote,
)


# STALE_ACTIVE_UNIVERSE_ASSUMPTION fixed: SILVERM was replaced by
# NATGASMINI in the Phase 6 MCX product migration. The active universe
# per mcx_version.PRODUCT_EPOCHS is now (CRUDEOILM, GOLDM, NATGASMINI).
TARGET_PRODUCTS = (
    "CRUDEOILM",
    "GOLDM",
    "NATGASMINI",
)


@pytest.fixture
def isolated_config(
    monkeypatch,
    tmp_path,
):
    path = (
        tmp_path
        / "exec_config.json"
    )

    monkeypatch.setattr(
        cfg,
        "CONFIG_PATH",
        str(path),
    )

    return path


def test_defaults_are_exact_three_and_uncalibrated(
    isolated_config,
):
    assert (
        cfg.SUPPORTED_PRODUCTS
        == TARGET_PRODUCTS
    )

    for product in TARGET_PRODUCTS:
        status = (
            cfg.calibration_status(
                product,
                provider="FYERS",
            )
        )

        assert (
            status[
                "entry_execution_calibrated"
            ]
            is False
        )


def test_legacy_unscoped_config_cannot_authorize_fyers(
    isolated_config,
):
    isolated_config.write_text(
        json.dumps({
            "CRUDEOILM": {
                "depth_quantity_semantics_verified":
                    True,
                "depth_quantity_unit":
                    "LEGACY",
                "execution_freshness_calibrated":
                    True,
                "execution_quote_max_age_seconds":
                    20,
            }
        }),
        encoding="utf-8",
    )

    status = (
        cfg.calibration_status(
            "CRUDEOILM",
            provider="FYERS",
        )
    )

    assert (
        status[
            "entry_execution_calibrated"
        ]
        is False
    )

    assert (
        status["reason"]
        == "LEGACY_OR_UNSCOPED_CONFIG_IGNORED"
    )


def test_other_provider_cannot_authorize_fyers(
    isolated_config,
):
    isolated_config.write_text(
        json.dumps({
            "schema_version": 2,
            "providers": {
                "ANGELONE": {
                    "CRUDEOILM": {
                        "calibration_provider":
                            "ANGELONE",
                        "depth_quantity_semantics_verified":
                            True,
                        "depth_quantity_unit":
                            "CONTRACT_UNITS",
                        "execution_freshness_calibrated":
                            True,
                        "execution_quote_max_age_seconds":
                            5,
                        "calibrated_at":
                            "2026-09-15T10:00:00+05:30",
                        "evidence_ref":
                            "old-provider-proof",
                        "evidence_kind":
                            "LIVE_MARKET_DEPTH",
                    }
                }
            },
        }),
        encoding="utf-8",
    )

    assert (
        cfg.is_entry_execution_calibrated(
            "CRUDEOILM",
            provider="FYERS",
        )
        is False
    )


def test_fyers_flags_without_live_evidence_are_insufficient(
    isolated_config,
):
    isolated_config.write_text(
        json.dumps({
            "schema_version": 2,
            "providers": {
                "FYERS": {
                    "CRUDEOILM": {
                        "calibration_provider":
                            "FYERS",
                        "depth_quantity_semantics_verified":
                            True,
                        "depth_quantity_unit":
                            "CONTRACT_UNITS",
                        "execution_freshness_calibrated":
                            True,
                        "execution_quote_max_age_seconds":
                            5,
                    }
                }
            },
        }),
        encoding="utf-8",
    )

    assert (
        cfg.is_entry_execution_calibrated(
            "CRUDEOILM",
            provider="FYERS",
        )
        is False
    )


def test_complete_fyers_live_evidence_authorizes_only_that_product(
    isolated_config,
):
    isolated_config.write_text(
        json.dumps({
            "schema_version": 2,
            "providers": {
                "FYERS": {
                    "CRUDEOILM": {
                        "calibration_provider":
                            "FYERS",
                        "depth_quantity_semantics_verified":
                            True,
                        "depth_quantity_unit":
                            "CONTRACT_UNITS",
                        "execution_freshness_calibrated":
                            True,
                        "execution_quote_max_age_seconds":
                            4.5,
                        "calibrated_at":
                            "2026-09-18T09:30:00+05:30",
                        "evidence_ref":
                            "fyers-depth-proof-001",
                        "evidence_kind":
                            "LIVE_MARKET_DEPTH",
                    }
                }
            },
        }),
        encoding="utf-8",
    )

    assert (
        cfg.is_entry_execution_calibrated(
            "CRUDEOILM",
            provider="FYERS",
        )
        is True
    )

    assert (
        cfg.get_execution_quote_max_age_seconds(
            "CRUDEOILM",
            provider="FYERS",
        )
        == 4.5
    )

    assert (
        cfg.is_entry_execution_calibrated(
            "GOLDM",
            provider="FYERS",
        )
        is False
    )


def _quote():
    return make_execution_quote(
        product="CRUDEOILM",
        option_symbol="MCX:TEST",
        token="FYERS-TOKEN",
        exchange="MCX",
        option_type="CE",
        strike=9500,
        expiry="2026-09-25",
        ltp=100.0,
        bids=[{
            "price": 99.95,
            "quantity": 20,
            "orders": 2,
        }],
        asks=[{
            "price": 100.05,
            "quantity": 20,
            "orders": 2,
        }],
        exchange_feed_time=1789725600,
        exchange_trade_time=1789725600,
        provider_received_at=(
            "2026-09-18T10:00:00+05:30"
        ),
        provider="FYERS",
        source_mode="REST_FULL",
        tick_size=0.05,
        raw_payload={
            "provider": "FYERS",
        },
    )


def test_uncalibrated_quote_remains_operational_for_exit(
    isolated_config,
):
    ok, quote = validate_quote(
        _quote(),
        expected_token="FYERS-TOKEN",
        expected_exchange="MCX",
        now_iso=(
            "2026-09-18T10:00:01+05:30"
        ),
    )

    assert ok is True

    assert (
        quote[
            "execution_freshness_status"
        ]
        == "OPERATIONAL_UNCALIBRATED"
    )

    assert (
        quote[
            "certification_freshness_calibrated"
        ]
        is False
    )


def test_operational_fallback_still_rejects_stale_quote(
    isolated_config,
):
    ok, quote = validate_quote(
        _quote(),
        expected_token="FYERS-TOKEN",
        expected_exchange="MCX",
        now_iso=(
            "2026-09-18T10:01:00+05:30"
        ),
    )

    assert ok is False

    assert (
        "STALE_QUOTE"
        in quote[
            "rejection_reasons"
        ]
    )


def test_paper_bot_blocks_new_entries_until_fyers_calibration():
    text = Path(
        "src/mcx/mcx_paper_bot.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "is_entry_execution_calibrated"
        in text
    )

    assert (
        "EXECUTION_CALIBRATION_BLOCKED"
        in text
    )


def test_countability_requires_fyers_provider_evidence():
    text = Path(
        "src/mcx/mcx_exec_countability.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "ENTRY_PROVIDER_MISMATCH"
        in text
    )

    assert (
        "EXIT_PROVIDER_MISMATCH"
        in text
    )

    assert (
        'provider="FYERS"'
        in text
    )


def test_global_certification_freshness_fallback_is_disabled():
    from mcx import mcx_exec_quote

    assert (
        mcx_exec_quote
        .EXECUTION_FRESHNESS_CALIBRATED
        is False
    )

    assert (
        mcx_exec_quote
        .EXECUTION_FRESHNESS_SOURCE
        == "PROVIDER_SCOPED_CALIBRATION_REQUIRED"
    )
