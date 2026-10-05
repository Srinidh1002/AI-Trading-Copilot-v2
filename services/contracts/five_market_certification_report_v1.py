"""Immutable final/in-progress five-market PAPER certification report."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


_STATUSES = {"IN_PROGRESS", "DIVERSITY_FAIL", "FAIL_ACCURACY", "PASS"}
_MARKETS = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")


@dataclass(frozen=True, slots=True)
class FiveMarketCertificationMarketReportV1:
    market: str
    strategy_version: str
    certification_epoch: str
    target_trade_count: int
    accepted_trade_count: int
    t1_first_wins: int
    sl_first_losses: int
    operational_completed_trades: int
    operational_net_pnl: float
    noncountable_completed_trades: int
    ambiguous_completed_trades: int
    distinct_trading_days: int
    distinct_regimes: int
    distinct_session_phases: int
    max_countable_per_day: int
    diversity_pass: bool
    accuracy_threshold_pass: bool
    state_counter_integrity: bool
    ledger_reconciliation_pass: bool
    final_status: str
    accepted_trade_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "five_market_certification_market_report.v1"

    def __post_init__(self) -> None:
        market = str(self.market or "").strip().upper()
        if market not in _MARKETS:
            raise ValueError("market")
        object.__setattr__(self, "market", market)
        for field in ("strategy_version", "certification_epoch"):
            value = str(getattr(self, field) or "").strip()
            if not value:
                raise ValueError(field)
            object.__setattr__(self, field, value)
        for field in (
            "target_trade_count",
            "accepted_trade_count",
            "t1_first_wins",
            "sl_first_losses",
            "operational_completed_trades",
            "noncountable_completed_trades",
            "ambiguous_completed_trades",
            "distinct_trading_days",
            "distinct_regimes",
            "distinct_session_phases",
            "max_countable_per_day",
        ):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(field)
        if self.target_trade_count != 100:
            raise ValueError("target_trade_count")
        if self.accepted_trade_count != self.t1_first_wins + self.sl_first_losses:
            raise ValueError("accepted counter coherence")
        if self.accepted_trade_count != len(self.accepted_trade_ids):
            raise ValueError("accepted id coherence")
        if len(set(self.accepted_trade_ids)) != len(self.accepted_trade_ids):
            raise ValueError("accepted trade IDs must be unique")
        if self.accepted_trade_count > 100:
            raise ValueError("fixed sample cannot exceed 100")
        if self.final_status not in _STATUSES:
            raise ValueError("final_status")
        if self.final_status == "PASS" and not (
            self.accepted_trade_count == 100
            and self.diversity_pass
            and self.accuracy_threshold_pass
            and self.state_counter_integrity
            and self.ledger_reconciliation_pass
        ):
            raise ValueError("PASS requires complete reconciled certification")
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode")
        if self.broker_order_submission or self.live_execution_eligible:
            raise ValueError("LIVE execution prohibited")
        if self.schema_version != "five_market_certification_market_report.v1":
            raise ValueError("schema_version")
        object.__setattr__(self, "operational_net_pnl", float(self.operational_net_pnl))
        object.__setattr__(
            self,
            "warnings",
            tuple(dict.fromkeys(str(item) for item in self.warnings if str(item))),
        )

    @property
    def certification_win_rate(self) -> float | None:
        if self.accepted_trade_count == 0:
            return None
        return self.t1_first_wins / self.accepted_trade_count * 100.0

    @property
    def remaining_trade_count(self) -> int:
        return 100 - self.accepted_trade_count

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["accepted_trade_ids"] = list(self.accepted_trade_ids)
        value["warnings"] = list(self.warnings)
        value["certification_win_rate"] = self.certification_win_rate
        value["remaining_trade_count"] = self.remaining_trade_count
        return value


@dataclass(frozen=True, slots=True)
class FiveMarketCertificationReportV1:
    generated_at: datetime
    release_commit: str
    markets: tuple[FiveMarketCertificationMarketReportV1, ...]
    execution_mode: str = "PAPER"
    live_broker_orders_prohibited: bool = True
    live_capital_prohibited: bool = True
    read_only: bool = True
    schema_version: str = "five_market_certification_report.v1"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.generated_at, datetime)
            or self.generated_at.tzinfo is None
            or self.generated_at.utcoffset() is None
        ):
            raise ValueError("generated_at")
        commit = str(self.release_commit or "").strip()
        if not commit:
            raise ValueError("release_commit")
        object.__setattr__(self, "release_commit", commit)
        if (
            not isinstance(self.markets, tuple)
            or tuple(item.market for item in self.markets) != _MARKETS
        ):
            raise ValueError("canonical five-market order required")
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode")
        if (
            not self.live_broker_orders_prohibited
            or not self.live_capital_prohibited
            or not self.read_only
        ):
            raise ValueError("report safety")
        if self.schema_version != "five_market_certification_report.v1":
            raise ValueError("schema_version")

    @property
    def all_markets_complete(self) -> bool:
        return all(item.accepted_trade_count == 100 for item in self.markets)

    @property
    def all_markets_pass(self) -> bool:
        return all(item.final_status == "PASS" for item in self.markets)

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "release_commit": self.release_commit,
            "markets": [item.to_dict() for item in self.markets],
            "all_markets_complete": self.all_markets_complete,
            "all_markets_pass": self.all_markets_pass,
            "execution_mode": self.execution_mode,
            "live_broker_orders_prohibited": self.live_broker_orders_prohibited,
            "live_capital_prohibited": self.live_capital_prohibited,
            "read_only": self.read_only,
            "schema_version": self.schema_version,
        }
