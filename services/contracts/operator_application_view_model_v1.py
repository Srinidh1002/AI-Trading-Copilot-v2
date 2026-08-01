"""Typed read-only operator application view model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _number(
    value: object,
    name: str,
    *,
    allow_negative: bool = False,
) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise ValueError(name)
    result = float(value)
    if not allow_negative and result < 0.0:
        raise ValueError(name)
    return result


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class OperatorMarketCardV1:
    title: str
    exchange: str
    score_label: str
    confidence_label: str
    direction_label: str
    eligibility_label: str
    freshness_label: str
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "title",
            "exchange",
            "score_label",
            "confidence_label",
            "direction_label",
            "eligibility_label",
            "freshness_label",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "reasons",
            _messages(self.reasons, "reasons"),
        )
        object.__setattr__(
            self,
            "rejection_reasons",
            _messages(
                self.rejection_reasons,
                "rejection_reasons",
            ),
        )


@dataclass(frozen=True, slots=True)
class OperatorRecommendationCardV1:
    action_label: str
    selected_market_label: str
    contract_label: str
    entry_label: str
    stop_label: str
    targets_label: str
    confidence_label: str
    explanation: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "action_label",
            "selected_market_label",
            "contract_label",
            "entry_label",
            "stop_label",
            "targets_label",
            "confidence_label",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "explanation",
            _messages(self.explanation, "explanation"),
        )


@dataclass(frozen=True, slots=True)
class OperatorCapitalCardV1:
    supplied_capital_label: str
    usable_capital_label: str
    position_size_label: str
    capital_required_label: str
    maximum_loss_label: str
    daily_risk_used_label: str

    def __post_init__(self) -> None:
        for name in (
            "supplied_capital_label",
            "usable_capital_label",
            "position_size_label",
            "capital_required_label",
            "maximum_loss_label",
            "daily_risk_used_label",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )


@dataclass(frozen=True, slots=True)
class OperatorActiveTradeCardV1:
    status_label: str
    contract_label: str
    premium_label: str
    pnl_label: str
    target_status_label: str
    stop_status_label: str
    instruction_label: str
    confidence_warning_label: str

    def __post_init__(self) -> None:
        for name in (
            "status_label",
            "contract_label",
            "premium_label",
            "pnl_label",
            "target_status_label",
            "stop_status_label",
            "instruction_label",
            "confidence_warning_label",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )


@dataclass(frozen=True, slots=True)
class OperatorHealthCardV1:
    status_label: str
    data_freshness_label: str
    data_connection_label: str
    broker_connection_label: str
    mode_label: str
    broker_submission_label: str
    emergency_halt_label: str
    runtime_label: str
    journal_label: str
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "status_label",
            "data_freshness_label",
            "data_connection_label",
            "broker_connection_label",
            "mode_label",
            "broker_submission_label",
            "emergency_halt_label",
            "runtime_label",
            "journal_label",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "warnings",
            _messages(self.warnings, "warnings"),
        )


@dataclass(frozen=True, slots=True)
class OperatorApplicationViewModelV1:
    SCHEMA_VERSION: ClassVar[str] = "operator_application_view_model.v1"

    view_model_id: str
    generated_at: datetime
    title: str
    subtitle: str
    selected_market_banner: str
    losing_market_banner: str
    nifty_card: OperatorMarketCardV1
    sensex_card: OperatorMarketCardV1
    recommendation_card: OperatorRecommendationCardV1
    capital_card: OperatorCapitalCardV1
    active_trade_card: OperatorActiveTradeCardV1
    health_card: OperatorHealthCardV1
    read_only_notice: str
    read_only: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "view_model_id",
            _text(self.view_model_id, "view_model_id"),
        )
        object.__setattr__(
            self,
            "generated_at",
            _aware(self.generated_at, "generated_at"),
        )
        for name in (
            "title",
            "subtitle",
            "selected_market_banner",
            "losing_market_banner",
            "read_only_notice",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        expected = {
            "nifty_card": OperatorMarketCardV1,
            "sensex_card": OperatorMarketCardV1,
            "recommendation_card": OperatorRecommendationCardV1,
            "capital_card": OperatorCapitalCardV1,
            "active_trade_card": OperatorActiveTradeCardV1,
            "health_card": OperatorHealthCardV1,
        }
        for name, expected_type in expected.items():
            if type(getattr(self, name)) is not expected_type:
                raise TypeError(name)

        if type(self.read_only) is not bool or self.read_only is not True:
            raise ValueError("view model must be read-only")
