"""Typed Task 6 operator snapshot runtime input contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.operator_application_snapshot_v1 import (
    OperatorActiveTradeStateV1,
    OperatorCapitalStateV1,
    OperatorMarketStateV1,
    OperatorRecommendationStateV1,
    OperatorSystemHealthV1,
)


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


@dataclass(frozen=True, slots=True)
class OperatorSnapshotRuntimeInputV1:
    SCHEMA_VERSION: ClassVar[str] = "operator_snapshot_runtime_input.v1"

    runtime_input_id: str
    generated_at: datetime
    nifty: OperatorMarketStateV1
    sensex: OperatorMarketStateV1
    recommendation: OperatorRecommendationStateV1
    capital: OperatorCapitalStateV1
    active_trade: OperatorActiveTradeStateV1
    system_health: OperatorSystemHealthV1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "runtime_input_id",
            _text(self.runtime_input_id, "runtime_input_id"),
        )
        object.__setattr__(
            self,
            "generated_at",
            _aware(self.generated_at, "generated_at"),
        )

        expected = {
            "nifty": OperatorMarketStateV1,
            "sensex": OperatorMarketStateV1,
            "recommendation": OperatorRecommendationStateV1,
            "capital": OperatorCapitalStateV1,
            "active_trade": OperatorActiveTradeStateV1,
            "system_health": OperatorSystemHealthV1,
        }
        for name, expected_type in expected.items():
            if type(getattr(self, name)) is not expected_type:
                raise TypeError(name)
