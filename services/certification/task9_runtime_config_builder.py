"""Construction and precedence boundary for ``Task9RuntimeConfigV1``.

This is intentionally not a launcher integration.  It creates the canonical
Task 9 configuration before later campaign, manifest, and provider stages.
"""
from __future__ import annotations

import importlib
from collections.abc import Mapping
from datetime import date
from typing import Any

from services.contracts.task9_runtime_config_v1 import Task9RuntimeConfigV1


# These are the established, non-secret values currently used by the focused
# Task 9 / Task 8 runtime seams.  Capital, risk fraction, maximum quantity,
# and policy references are intentionally absent: they are not proven static
# Task 9 authorities and must be supplied by the operational caller.
_STATIC_DEFAULTS: dict[str, object] = {
    "timezone": "Asia/Kolkata",  # config.py TIMEZONE
    "maximum_daily_loss_fraction": 0.05,  # config.py MAX_DAILY_LOSS
    "maximum_lots": 3,  # Task 8 selected-market P6 bundle
    "maximum_spread_fraction": 0.10,  # Task 8 selected-market P6 bundle
    "parent_cycle_cadence_seconds": 60.0,  # Task 9 launcher default
    "collector_heartbeat_seconds": 5.0,  # services.config.settings REFRESH_INTERVAL
    "market_quote_max_age_seconds": 300.0,  # market-data freshness policy
    "option_quote_max_age_seconds": 300.0,  # canonical Angel FULL quote freshness
    "instrument_master_max_age_seconds": 86400.0,  # Angel master default
    # Names only: the builder never reads the values of these variables.
    "angel_api_key_env_name": "ANGEL_API_KEY",
    "angel_client_id_env_name": "ANGEL_CLIENT_ID",
    "angel_pin_env_name": "ANGEL_PIN",
    "angel_totp_secret_env_name": "ANGEL_TOTP_SECRET",
}


def _legacy_candidates_from_repository() -> dict[str, object]:
    """Read only relevant legacy values at builder call time.

    No secret value is read or returned.  This deliberately records the
    untyped percentage value as a distinct candidate; it is never converted to
    a decimal risk fraction.
    """
    config = importlib.import_module("config")
    runtime = importlib.import_module("services.trading_runtime_config")
    return {
        "config_capital": config.DEFAULT_CAPITAL,
        "trading_runtime_capital": runtime.DEFAULT_CAPITAL,
        "config_risk_fraction": config.RISK_PER_TRADE,
        "trading_runtime_risk_percent": runtime.DEFAULT_RISK_PER_TRADE_PERCENT,
        "legacy_broker": config.BROKER,
        "legacy_enable_live_trading": config.ENABLE_LIVE_TRADING,
    }


def detect_task9_legacy_conflicts(legacy_values: Mapping[str, object]) -> frozenset[str]:
    """Return only bounded capital/risk migration conflicts.

    Risk values with different units are always a conflict.  A percent value
    is not transformed or guessed to be a fraction.
    """
    if not isinstance(legacy_values, Mapping):
        raise TypeError("legacy_values")
    conflicts: set[str] = set()
    capitals = {
        legacy_values[name]
        for name in ("config_capital", "trading_runtime_capital", "settings_capital")
        if legacy_values.get(name) is not None
    }
    if len(capitals) > 1:
        conflicts.add("capital")
    fractions = {
        legacy_values[name]
        for name in ("config_risk_fraction", "settings_risk_fraction")
        if legacy_values.get(name) is not None
    }
    if len(fractions) > 1 or legacy_values.get("trading_runtime_risk_percent") is not None:
        conflicts.add("risk_fraction")
    return frozenset(conflicts)


def _static_values(static_values: Mapping[str, object] | None) -> dict[str, object]:
    if static_values is not None and not isinstance(static_values, Mapping):
        raise TypeError("static_values")
    values = dict(_STATIC_DEFAULTS)
    if static_values is not None:
        values.update(static_values)
    return values


def _required(value: object, name: str) -> object:
    if value is None:
        raise ValueError(f"{name} requires an explicit canonical value")
    return value


def build_task9_runtime_config(
    *,
    runtime_config_id: str,
    runtime_config_version: str,
    campaign_registry_location: str,
    campaign_id: str,
    market_date: date,
    official_run_id: str,
    official_root: str,
    certification_registry_root: str,
    authoritative_persistence_root: str,
    dashboard_publication_location: str,
    available_capital: float | None = None,
    risk_fraction: float | None = None,
    maximum_quantity: int | None = None,
    policy_references: Mapping[str, str] | None = None,
    run_classification: str = "OFFICIAL_CERTIFICATION",
    execution_mode: str = "PAPER",
    broker_order_submission: bool = False,
    live_execution_eligible: bool = False,
    emergency_halt_enabled: bool = False,
    emergency_halt_reason: str | None = None,
    static_values: Mapping[str, object] | None = None,
    legacy_values: Mapping[str, object] | None = None,
) -> Task9RuntimeConfigV1:
    """Build a canonical config with frozen explicit > static precedence.

    Explicit operational arguments win over legacy candidates.  Ambiguous
    capital and risk have no static fallback: callers must provide their
    canonical decimal values.  Legacy configuration is diagnostic-only and
    never supplies a Task 9 value or safety state.
    """
    if execution_mode != "PAPER":
        raise ValueError("execution_mode")
    if broker_order_submission is not False:
        raise ValueError("broker_order_submission")
    if live_execution_eligible is not False:
        raise ValueError("live_execution_eligible")

    values = _static_values(static_values)
    candidates = (
        dict(legacy_values)
        if legacy_values is not None
        else _legacy_candidates_from_repository()
    )
    if not isinstance(candidates, Mapping):
        raise TypeError("legacy_values")
    # The result is intentionally calculated even when explicit inputs settle
    # it: that keeps migration evidence inspectable without granting legacy
    # values any authority.
    detect_task9_legacy_conflicts(candidates)

    return Task9RuntimeConfigV1(
        runtime_config_id=runtime_config_id,
        runtime_config_version=runtime_config_version,
        market_date=market_date,
        campaign_registry_location=campaign_registry_location,
        campaign_id=campaign_id,
        official_run_id=official_run_id,
        official_root=official_root,
        certification_registry_root=certification_registry_root,
        authoritative_persistence_root=authoritative_persistence_root,
        dashboard_publication_location=dashboard_publication_location,
        available_capital=_required(available_capital, "available_capital"),
        trade_risk_fraction=_required(risk_fraction, "risk_fraction"),
        maximum_quantity=_required(maximum_quantity, "maximum_quantity"),
        policy_references=_required(policy_references, "policy_references"),
        timezone=values["timezone"],
        run_classification=run_classification,
        maximum_daily_loss_fraction=values["maximum_daily_loss_fraction"],
        maximum_lots=values["maximum_lots"],
        maximum_spread_fraction=values["maximum_spread_fraction"],
        parent_cycle_cadence_seconds=values["parent_cycle_cadence_seconds"],
        collector_heartbeat_seconds=values["collector_heartbeat_seconds"],
        market_quote_max_age_seconds=values["market_quote_max_age_seconds"],
        option_quote_max_age_seconds=values["option_quote_max_age_seconds"],
        instrument_master_max_age_seconds=values["instrument_master_max_age_seconds"],
        angel_api_key_env_name=values["angel_api_key_env_name"],
        angel_client_id_env_name=values["angel_client_id_env_name"],
        angel_pin_env_name=values["angel_pin_env_name"],
        angel_totp_secret_env_name=values["angel_totp_secret_env_name"],
        emergency_halt_enabled=emergency_halt_enabled,
        emergency_halt_reason=emergency_halt_reason,
        execution_mode=execution_mode,
        broker_order_submission=broker_order_submission,
        live_execution_eligible=live_execution_eligible,
    )

