"""Immutable PAPER certification dashboard read model."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import ClassVar


def _text(value: object, name: str) -> str:
    if type(value) is not str:
        raise TypeError(name)
    cleaned = value.strip()
    if not cleaned:
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


def _date(value: object, name: str) -> date:
    if type(value) is not date:
        raise TypeError(name)
    return value


def _count(value: object, name: str) -> int:
    if (
        type(value) is not int
        or isinstance(value, bool)
        or value < 0
    ):
        raise ValueError(name)
    return value


def _number(value: object, name: str) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
    ):
        raise ValueError(name)
    return float(value)


def _optional_number(
    value: object,
    name: str,
) -> float | None:
    if value is None:
        return None
    return _number(value, name)


def _distribution(
    value: object,
    name: str,
) -> tuple[tuple[str, int], ...]:
    if type(value) is not tuple:
        raise TypeError(name)
    seen = set()
    result = []
    for item in value:
        if type(item) is not tuple or len(item) != 2:
            raise TypeError(name)
        key = _text(item[0], name)
        if key in seen:
            raise ValueError(f"duplicate {name} key")
        seen.add(key)
        result.append((key, _count(item[1], name)))
    return tuple(sorted(result))


@dataclass(frozen=True, slots=True)
class DashboardCertificationMarketViewV1:
    market: str
    prediction_count: int
    official_count: int
    success_count: int
    failure_count: int
    closed_trade_count: int
    gross_pnl: float
    net_pnl: float
    reliability_percent: float | None
    schema_version: str = "dashboard_certification_market_view.v1"

    def __post_init__(self) -> None:
        market = _text(self.market, "market").upper()
        if market not in {"NIFTY", "SENSEX"}:
            raise ValueError("market")
        object.__setattr__(self, "market", market)
        for name in (
            "prediction_count",
            "official_count",
            "success_count",
            "failure_count",
            "closed_trade_count",
        ):
            object.__setattr__(
                self,
                name,
                _count(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "gross_pnl",
            _number(self.gross_pnl, "gross_pnl"),
        )
        object.__setattr__(
            self,
            "net_pnl",
            _number(self.net_pnl, "net_pnl"),
        )
        reliability = _optional_number(
            self.reliability_percent,
            "reliability_percent",
        )
        if reliability is not None and not 0.0 <= reliability <= 100.0:
            raise ValueError("reliability_percent")
        object.__setattr__(
            self,
            "reliability_percent",
            reliability,
        )
        if (
            self.schema_version
            != "dashboard_certification_market_view.v1"
        ):
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DashboardCertificationViewV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "dashboard_certification_view.v1"
    )

    view_id: str
    generated_at: datetime
    as_of_date: date
    daily_report_id: str
    weekly_report_id: str | None
    monthly_report_id: str | None
    starting_capital: float
    ending_capital: float
    net_pnl: float
    official_prediction_count: int
    pending_prediction_count: int
    excluded_prediction_count: int
    closed_trade_count: int
    win_count: int
    loss_count: int
    break_even_count: int
    no_trade_cycle_count: int
    maximum_drawdown_amount: float
    maximum_drawdown_percent: float
    expectancy: float | None
    reliability_percent: float | None
    incident_count: int
    unresolved_incident_count: int
    duplicate_attempt_count: int
    market_views: tuple[DashboardCertificationMarketViewV1, ...]
    action_distribution: tuple[tuple[str, int], ...]
    outcome_distribution: tuple[tuple[str, int], ...]
    reconciliation_distribution: tuple[tuple[str, int], ...]
    incident_distribution: tuple[tuple[str, int], ...]
    duplicate_distribution: tuple[tuple[str, int], ...]
    unresolved_prediction_ids: tuple[str, ...]
    excluded_prediction_ids: tuple[str, ...]
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "view_id",
            "daily_report_id",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        for name in (
            "weekly_report_id",
            "monthly_report_id",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    _text(value, name),
                )

        object.__setattr__(
            self,
            "generated_at",
            _aware(self.generated_at, "generated_at"),
        )
        object.__setattr__(
            self,
            "as_of_date",
            _date(self.as_of_date, "as_of_date"),
        )
        for name in (
            "starting_capital",
            "ending_capital",
            "net_pnl",
            "maximum_drawdown_amount",
            "maximum_drawdown_percent",
        ):
            object.__setattr__(
                self,
                name,
                _number(getattr(self, name), name),
            )
        if not math.isclose(
            self.starting_capital + self.net_pnl,
            self.ending_capital,
            abs_tol=1e-9,
        ):
            raise ValueError("capital reconciliation")
        if (
            self.maximum_drawdown_amount < 0.0
            or self.maximum_drawdown_percent < 0.0
        ):
            raise ValueError("drawdown")

        for name in (
            "official_prediction_count",
            "pending_prediction_count",
            "excluded_prediction_count",
            "closed_trade_count",
            "win_count",
            "loss_count",
            "break_even_count",
            "no_trade_cycle_count",
            "incident_count",
            "unresolved_incident_count",
            "duplicate_attempt_count",
        ):
            object.__setattr__(
                self,
                name,
                _count(getattr(self, name), name),
            )
        if (
            self.win_count
            + self.loss_count
            + self.break_even_count
            != self.closed_trade_count
        ):
            raise ValueError("closed trade reconciliation")
        if self.unresolved_incident_count > self.incident_count:
            raise ValueError("incident reconciliation")

        for name in ("expectancy", "reliability_percent"):
            value = _optional_number(getattr(self, name), name)
            if (
                name == "reliability_percent"
                and value is not None
                and not 0.0 <= value <= 100.0
            ):
                raise ValueError(name)
            object.__setattr__(self, name, value)

        if type(self.market_views) is not tuple or any(
            type(item) is not DashboardCertificationMarketViewV1
            for item in self.market_views
        ):
            raise TypeError("market_views")
        if len({item.market for item in self.market_views}) != len(
            self.market_views
        ):
            raise ValueError("duplicate market view")

        for name in (
            "action_distribution",
            "outcome_distribution",
            "reconciliation_distribution",
            "incident_distribution",
            "duplicate_distribution",
        ):
            object.__setattr__(
                self,
                name,
                _distribution(getattr(self, name), name),
            )

        for name in (
            "unresolved_prediction_ids",
            "excluded_prediction_ids",
        ):
            value = getattr(self, name)
            if type(value) is not tuple:
                raise TypeError(name)
            cleaned = tuple(_text(item, name) for item in value)
            if len(set(cleaned)) != len(cleaned):
                raise ValueError(f"duplicate {name}")
            object.__setattr__(self, name, cleaned)

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.read_only is not True
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "PAPER-only read-only certification view"
            )

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["generated_at"] = self.generated_at.isoformat()
        value["as_of_date"] = self.as_of_date.isoformat()
        value["market_views"] = [
            item.to_dict()
            for item in self.market_views
        ]
        for name in (
            "action_distribution",
            "outcome_distribution",
            "reconciliation_distribution",
            "incident_distribution",
            "duplicate_distribution",
        ):
            value[name] = dict(getattr(self, name))
        value["unresolved_prediction_ids"] = list(
            self.unresolved_prediction_ids
        )
        value["excluded_prediction_ids"] = list(
            self.excluded_prediction_ids
        )
        return value

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def semantic_hash(self) -> str:
        return hashlib.sha256(
            self.to_json().encode("utf-8")
        ).hexdigest()
