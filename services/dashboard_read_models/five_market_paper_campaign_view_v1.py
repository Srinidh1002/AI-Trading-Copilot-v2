"""Immutable read-only view of the active five-market PAPER campaign."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Mapping


_MARKETS = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")


def _aware(value: datetime, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


@dataclass(frozen=True, slots=True)
class FiveMarketPaperMarketViewV1:
    market: str
    strategy_version: str
    certification_epoch: str
    certification_eligible: bool
    certification_counter: int
    certification_wins: int
    certification_losses: int
    target_trade_count: int
    operational_completed_trades: int
    operational_wins: int
    operational_losses: int
    operational_net_pnl: float
    noncountable_completed_trades: int
    active_position_count: int
    active_trade_id: str | None = None
    active_first_touch: str | None = None
    execution_mode: str = "PAPER"
    broker_submission: bool = False
    live_execution: bool = False
    source_schema: str = ""
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        market = str(self.market or "").strip().upper()
        if market not in _MARKETS:
            raise ValueError("market")
        object.__setattr__(self, "market", market)
        for name in ("strategy_version", "certification_epoch", "source_schema"):
            value = str(getattr(self, name) or "").strip()
            if not value:
                raise ValueError(name)
            object.__setattr__(self, name, value)
        for name in (
            "certification_counter",
            "certification_wins",
            "certification_losses",
            "target_trade_count",
            "operational_completed_trades",
            "operational_wins",
            "operational_losses",
            "noncountable_completed_trades",
            "active_position_count",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(name)
        if self.certification_counter != (
            self.certification_wins + self.certification_losses
        ):
            raise ValueError("certification counter coherence")
        if self.certification_counter > self.target_trade_count:
            raise ValueError("certification counter exceeds target")
        if self.noncountable_completed_trades > self.operational_completed_trades:
            raise ValueError("noncountable completed trades")
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode")
        if self.broker_submission is not False or self.live_execution is not False:
            raise ValueError("PAPER safety")
        object.__setattr__(
            self,
            "operational_net_pnl",
            float(self.operational_net_pnl),
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(dict.fromkeys(str(item) for item in self.warnings if str(item))),
        )

    @property
    def remaining_trade_count(self) -> int:
        return max(0, self.target_trade_count - self.certification_counter)

    @property
    def certification_win_rate(self) -> float | None:
        if self.certification_counter == 0:
            return None
        return (
            self.certification_wins
            / self.certification_counter
            * 100.0
        )

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["remaining_trade_count"] = self.remaining_trade_count
        value["certification_win_rate"] = self.certification_win_rate
        value["warnings"] = list(self.warnings)
        return value


@dataclass(frozen=True, slots=True)
class FiveMarketPaperCampaignViewV1:
    generated_at: datetime
    release_commit: str
    markets: tuple[FiveMarketPaperMarketViewV1, ...]
    execution_mode: str = "PAPER"
    live_broker_orders_prohibited: bool = True
    live_capital_prohibited: bool = True
    read_only: bool = True
    schema_version: str = "five_market_paper_campaign_view.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", _aware(self.generated_at, "generated_at"))
        commit = str(self.release_commit or "").strip()
        if not commit:
            raise ValueError("release_commit")
        object.__setattr__(self, "release_commit", commit)
        if (
            not isinstance(self.markets, tuple)
            or tuple(item.market for item in self.markets) != _MARKETS
        ):
            raise ValueError("markets must be canonical five-market order")
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode")
        if (
            self.live_broker_orders_prohibited is not True
            or self.live_capital_prohibited is not True
            or self.read_only is not True
        ):
            raise ValueError("campaign safety")
        if self.schema_version != "five_market_paper_campaign_view.v1":
            raise ValueError("schema_version")

    @property
    def total_accepted_certification_trades(self) -> int:
        return sum(item.certification_counter for item in self.markets)

    @property
    def total_operational_pnl(self) -> float:
        return sum(item.operational_net_pnl for item in self.markets)

    def by_market(self) -> Mapping[str, FiveMarketPaperMarketViewV1]:
        return {item.market: item for item in self.markets}

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "release_commit": self.release_commit,
            "markets": [item.to_dict() for item in self.markets],
            "total_accepted_certification_trades": (
                self.total_accepted_certification_trades
            ),
            "total_operational_pnl": self.total_operational_pnl,
            "execution_mode": self.execution_mode,
            "live_broker_orders_prohibited": self.live_broker_orders_prohibited,
            "live_capital_prohibited": self.live_capital_prohibited,
            "read_only": self.read_only,
            "schema_version": self.schema_version,
        }
