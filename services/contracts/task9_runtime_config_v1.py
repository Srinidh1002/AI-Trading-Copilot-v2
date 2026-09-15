"""Immutable, PAPER-only startup configuration for the Task 9 runtime.

This module is deliberately an additive authority boundary.  It validates
operational input but does not read the environment, contact providers, create
directories, or alter any launcher behaviour.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from services.contracts.task9_run_classification_v1 import (
    validate_task9_run_classification,
)
from services.underlying_registry import UnderlyingRegistry


TASK9_RUNTIME_CONFIG_SCHEMA_VERSION = "task9_runtime_config.v1"
_SCHEMA_VERSION = TASK9_RUNTIME_CONFIG_SCHEMA_VERSION
_REFERENCE_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
_POLICY_NAMES = frozenset({
    "canonical_directional", "session", "risk", "contract_selection",
    "lifecycle", "counting", "failure_disposition", "contract_spread",
    "liquidity", "minimum_risk_reward", "stop_target", "portfolio_concurrency",
})
_FEATURE_NAMES = frozenset({
    "angel_spot", "angel_option_full", "angel_greeks", "india_vix",
    "market_breadth", "fii_dii", "events", "global", "news", "llm",
})


class ProviderFeatureStateV1(str, Enum):
    """Configured intent, not a live provider capability result."""

    ENABLED_REQUIRED = "ENABLED_REQUIRED"
    ENABLED_OPTIONAL = "ENABLED_OPTIONAL"
    CAPABILITY_AWARE = "CAPABILITY_AWARE"
    PROVIDER_NOT_SELECTED = "PROVIDER_NOT_SELECTED"
    DISABLED = "DISABLED"
    OPTIONAL_FUTURE = "OPTIONAL_FUTURE"


def _text(value: object, name: str) -> str:
    if type(value) is not str or not (value := value.strip()):
        raise ValueError(name)
    return value


def _path(value: object, name: str) -> str:
    value = _text(value, name)
    # A relative path is an intentional, deterministic startup reference.
    return Path(value).as_posix()


def _positive(value: object, name: str, *, maximum: float | None = None) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise ValueError(name)
    value = float(value)
    if not math.isfinite(value) or value <= 0 or (maximum is not None and value > maximum):
        raise ValueError(name)
    return value


def _nonnegative_int(value: object, name: str) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise ValueError(name)
    return value


def _reference_name(value: object, name: str) -> str | None:
    if value is None:
        return None
    value = _text(value, name)
    if not _REFERENCE_NAME.fullmatch(value):
        raise ValueError(name)
    return value


@dataclass(frozen=True, slots=True)
class Task9MarketRuntimeIdentityV1:
    """One exact underlying/venue identity, validated against UnderlyingRegistry."""

    market: str
    exchange: str
    spot_token: str
    option_exchange: str
    provider_market_name: str | None = None

    def __post_init__(self) -> None:
        market = _text(self.market, "market").upper()
        authority = UnderlyingRegistry.get(market)
        if market not in {"NIFTY", "SENSEX"}:
            raise ValueError("market")
        exchange = _text(self.exchange, "exchange").upper()
        option_exchange = _text(self.option_exchange, "option_exchange").upper()
        spot_token = _text(self.spot_token, "spot_token")
        if (exchange, option_exchange, spot_token) != (
            authority.exchange, authority.option_exchange, authority.symboltoken,
        ):
            raise ValueError("market identity")
        provider_name = self.provider_market_name
        if provider_name is not None:
            provider_name = _text(provider_name, "provider_market_name")
            # The documented Angel spelling is allowed only for NIFTY; it is
            # still bound to the canonical NIFTY identity above.
            if market == "NIFTY" and provider_name.upper() not in {"NIFTY", "NIFTY 50"}:
                raise ValueError("provider_market_name")
            if market == "SENSEX" and provider_name.upper() != "SENSEX":
                raise ValueError("provider_market_name")
        object.__setattr__(self, "market", market)
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "option_exchange", option_exchange)
        object.__setattr__(self, "spot_token", spot_token)
        object.__setattr__(self, "provider_market_name", provider_name)

    def to_dict(self) -> dict[str, str | None]:
        return {
            "market": self.market, "exchange": self.exchange,
            "spot_token": self.spot_token, "option_exchange": self.option_exchange,
            "provider_market_name": self.provider_market_name,
        }


def _default_markets() -> tuple[Task9MarketRuntimeIdentityV1, ...]:
    return (
        Task9MarketRuntimeIdentityV1("NIFTY", "NSE", "99926000", "NFO", "Nifty 50"),
        Task9MarketRuntimeIdentityV1("SENSEX", "BSE", "99919000", "BFO", "SENSEX"),
    )


def _default_provider_features() -> Mapping[str, ProviderFeatureStateV1]:
    return MappingProxyType({
        "angel_spot": ProviderFeatureStateV1.ENABLED_REQUIRED,
        "angel_option_full": ProviderFeatureStateV1.ENABLED_REQUIRED,
        "angel_greeks": ProviderFeatureStateV1.CAPABILITY_AWARE,
        "india_vix": ProviderFeatureStateV1.ENABLED_OPTIONAL,
        "market_breadth": ProviderFeatureStateV1.PROVIDER_NOT_SELECTED,
        "fii_dii": ProviderFeatureStateV1.PROVIDER_NOT_SELECTED,
        "events": ProviderFeatureStateV1.PROVIDER_NOT_SELECTED,
        "global": ProviderFeatureStateV1.PROVIDER_NOT_SELECTED,
        "news": ProviderFeatureStateV1.PROVIDER_NOT_SELECTED,
        "llm": ProviderFeatureStateV1.OPTIONAL_FUTURE,
    })


@dataclass(frozen=True, slots=True)
class Task9RuntimeConfigV1:
    """Canonical startup identity and non-secret configuration for Task 9."""

    runtime_config_id: str
    runtime_config_version: str
    market_date: date
    campaign_registry_location: str
    campaign_id: str
    official_run_id: str
    official_root: str
    certification_registry_root: str
    authoritative_persistence_root: str
    dashboard_publication_location: str
    available_capital: float
    trade_risk_fraction: float
    maximum_daily_loss_fraction: float
    maximum_lots: int
    maximum_quantity: int
    maximum_spread_fraction: float
    parent_cycle_cadence_seconds: float
    collector_heartbeat_seconds: float
    market_quote_max_age_seconds: float
    option_quote_max_age_seconds: float
    instrument_master_max_age_seconds: float
    policy_references: Mapping[str, str]
    timezone: str = "Asia/Kolkata"
    run_classification: str = "OFFICIAL_CERTIFICATION"
    markets: tuple[Task9MarketRuntimeIdentityV1, ...] = field(default_factory=_default_markets)
    provider_features: Mapping[str, ProviderFeatureStateV1] = field(default_factory=_default_provider_features)
    angel_api_key_env_name: str | None = None
    angel_client_id_env_name: str | None = None
    angel_pin_env_name: str | None = None
    angel_totp_secret_env_name: str | None = None
    emergency_halt_enabled: bool = False
    emergency_halt_reason: str | None = None
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False
    schema_version: str = _SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError("schema_version")
        for name in ("runtime_config_id", "runtime_config_version", "campaign_id", "official_run_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("campaign_registry_location", "official_root", "certification_registry_root", "authoritative_persistence_root", "dashboard_publication_location"):
            object.__setattr__(self, name, _path(getattr(self, name), name))
        if type(self.market_date) is not date:
            raise ValueError("market_date")
        timezone = _text(self.timezone, "timezone")
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone") from exc
        object.__setattr__(self, "timezone", timezone)
        object.__setattr__(self, "run_classification", validate_task9_run_classification(self.run_classification))
        if self.execution_mode != "PAPER" or self.broker_order_submission is not False or self.live_execution_eligible is not False:
            raise ValueError("Task 9 runtime config must remain PAPER-only")
        if type(self.emergency_halt_enabled) is not bool:
            raise TypeError("emergency_halt_enabled")
        if self.emergency_halt_reason is not None:
            object.__setattr__(self, "emergency_halt_reason", _text(self.emergency_halt_reason, "emergency_halt_reason"))
        if self.emergency_halt_enabled and self.emergency_halt_reason is None:
            raise ValueError("emergency_halt_reason")
        if not isinstance(self.markets, tuple) or len(self.markets) != 2 or any(type(item) is not Task9MarketRuntimeIdentityV1 for item in self.markets):
            raise ValueError("markets")
        if tuple(item.market for item in self.markets) != ("NIFTY", "SENSEX"):
            raise ValueError("markets")
        for name in ("available_capital", "parent_cycle_cadence_seconds", "collector_heartbeat_seconds", "market_quote_max_age_seconds", "option_quote_max_age_seconds", "instrument_master_max_age_seconds"):
            object.__setattr__(self, name, _positive(getattr(self, name), name))
        for name in ("trade_risk_fraction", "maximum_daily_loss_fraction", "maximum_spread_fraction"):
            object.__setattr__(self, name, _positive(getattr(self, name), name, maximum=1.0))
        for name in ("maximum_lots", "maximum_quantity"):
            object.__setattr__(self, name, _nonnegative_int(getattr(self, name), name))
        if not isinstance(self.policy_references, Mapping) or set(self.policy_references) != _POLICY_NAMES:
            raise ValueError("policy_references")
        object.__setattr__(self, "policy_references", MappingProxyType(dict(sorted((key, _text(value, f"policy_references.{key}")) for key, value in self.policy_references.items()))))
        if not isinstance(self.provider_features, Mapping) or set(self.provider_features) != _FEATURE_NAMES:
            raise ValueError("provider_features")
        normalized_features: dict[str, ProviderFeatureStateV1] = {}
        for name, state in self.provider_features.items():
            try:
                normalized_features[name] = ProviderFeatureStateV1(state)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"provider_features.{name}") from exc
        expected_features = dict(_default_provider_features())
        # LLM is deliberately not an authority for Task 9.  Operators may
        # make that explicit as DISABLED without conflating it with a provider
        # that simply has not been selected yet.
        if normalized_features.get("llm") is ProviderFeatureStateV1.DISABLED:
            expected_features["llm"] = ProviderFeatureStateV1.DISABLED
        if normalized_features != expected_features:
            raise ValueError("provider_features")
        object.__setattr__(self, "provider_features", MappingProxyType(dict(sorted(normalized_features.items()))))
        for name in ("angel_api_key_env_name", "angel_client_id_env_name", "angel_pin_env_name", "angel_totp_secret_env_name"):
            object.__setattr__(self, name, _reference_name(getattr(self, name), name))

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic, JSON-safe, secret-free representation."""
        return {
            "schema_version": self.schema_version,
            "runtime_config_id": self.runtime_config_id,
            "runtime_config_version": self.runtime_config_version,
            "execution_mode": self.execution_mode,
            "broker_order_submission": self.broker_order_submission,
            "live_execution_eligible": self.live_execution_eligible,
            "emergency_halt_enabled": self.emergency_halt_enabled,
            "emergency_halt_reason": self.emergency_halt_reason,
            "timezone": self.timezone,
            "market_date": self.market_date.isoformat(),
            "markets": [item.to_dict() for item in self.markets],
            "campaign_registry_location": self.campaign_registry_location,
            "campaign_id": self.campaign_id,
            "official_run_id": self.official_run_id,
            "official_root": self.official_root,
            "run_classification": self.run_classification,
            "provider_features": {name: state.value for name, state in self.provider_features.items()},
            "angel_api_key_env_name": self.angel_api_key_env_name,
            "angel_client_id_env_name": self.angel_client_id_env_name,
            "angel_pin_env_name": self.angel_pin_env_name,
            "angel_totp_secret_env_name": self.angel_totp_secret_env_name,
            "parent_cycle_cadence_seconds": self.parent_cycle_cadence_seconds,
            "collector_heartbeat_seconds": self.collector_heartbeat_seconds,
            "market_quote_max_age_seconds": self.market_quote_max_age_seconds,
            "option_quote_max_age_seconds": self.option_quote_max_age_seconds,
            "instrument_master_max_age_seconds": self.instrument_master_max_age_seconds,
            "available_capital": self.available_capital,
            "trade_risk_fraction": self.trade_risk_fraction,
            "maximum_daily_loss_fraction": self.maximum_daily_loss_fraction,
            "maximum_lots": self.maximum_lots,
            "maximum_quantity": self.maximum_quantity,
            "maximum_spread_fraction": self.maximum_spread_fraction,
            "certification_registry_root": self.certification_registry_root,
            "authoritative_persistence_root": self.authoritative_persistence_root,
            "dashboard_publication_location": self.dashboard_publication_location,
            "policy_references": dict(self.policy_references),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Task9RuntimeConfigV1":
        if not isinstance(value, Mapping):
            raise TypeError("runtime config")
        payload = dict(value)
        try:
            payload["market_date"] = date.fromisoformat(payload["market_date"])
            payload["markets"] = tuple(Task9MarketRuntimeIdentityV1(**item) for item in payload["markets"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("runtime config serialization") from exc
        return cls(**payload)


def build_task9_runtime_config(**kwargs: Any) -> Task9RuntimeConfigV1:
    """Build one validated canonical Task 9 runtime configuration."""
    return Task9RuntimeConfigV1(**kwargs)
