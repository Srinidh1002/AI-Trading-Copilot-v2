"""Canonical previous-session and pre-market intelligence contracts.

These contracts describe evidence.  They do not fetch data, choose trades,
change thresholds, submit orders, or confer certification credit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math

from services.core.five_market_universe_v2 import (
    get_target_market,
)


EVIDENCE_STATUSES = frozenset(
    {
        "AVAILABLE",
        "UNAVAILABLE",
        "STALE",
        "UNVERIFIED",
        "NOT_APPLICABLE",
    }
)

DIRECTIONS = frozenset(
    {
        "UP",
        "DOWN",
        "FLAT",
    }
)

PREVIOUS_DAY_TYPES = frozenset(
    {
        "TREND_UP",
        "TREND_DOWN",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "RANGE_DAY",
    }
)

GLOBAL_RISK_SENTIMENTS = frozenset(
    {
        "RISK_ON",
        "RISK_OFF",
        "NEUTRAL",
        "UNKNOWN",
    }
)

FLOW_BIASES = frozenset(
    {
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "UNKNOWN",
    }
)


def _norm(
    value: object,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        return ""

    return " ".join(
        value.strip().upper().split()
    )


def _text(
    value: object,
) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    return value or None


def _finite(
    value: object,
) -> bool:
    return (
        isinstance(
            value,
            (int, float),
        )
        and not isinstance(
            value,
            bool,
        )
        and math.isfinite(
            float(value)
        )
    )


def _aware(
    value: object,
) -> bool:
    return (
        isinstance(
            value,
            datetime,
        )
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _evidence_status(
    value: object,
) -> str:
    status = _norm(
        value
    )

    if status not in EVIDENCE_STATUSES:
        raise ValueError(
            "Invalid evidence status."
        )

    return status


@dataclass(frozen=True, slots=True)
class PreviousSessionIntelligenceV2:
    market_symbol: str
    session_date: date

    open: float
    high: float
    low: float
    close: float

    range_points: float
    range_pct: float
    body_pct: float

    direction: str
    close_location: float
    day_type: str

    atr14: float | None

    source: str
    observed_at: datetime

    evidence_status: str = "AVAILABLE"
    schema_version: str = (
        "previous_session_intelligence.v2"
    )

    def __post_init__(
        self,
    ) -> None:
        market = get_target_market(
            self.market_symbol
        )

        if not isinstance(
            self.session_date,
            date,
        ):
            raise ValueError(
                "Session date is required."
            )

        values = (
            self.open,
            self.high,
            self.low,
            self.close,
        )

        if not all(
            _finite(value)
            and float(value) > 0
            for value in values
        ):
            raise ValueError(
                "Previous-session OHLC must be positive finite values."
            )

        if self.high < max(
            self.open,
            self.close,
            self.low,
        ):
            raise ValueError(
                "Invalid previous-session high."
            )

        if self.low > min(
            self.open,
            self.close,
            self.high,
        ):
            raise ValueError(
                "Invalid previous-session low."
            )

        expected_range = (
            float(self.high)
            - float(self.low)
        )

        if (
            not _finite(
                self.range_points
            )
            or self.range_points < 0
            or not math.isclose(
                float(self.range_points),
                expected_range,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
        ):
            raise ValueError(
                "Previous-session range mismatch."
            )

        if (
            not _finite(
                self.range_pct
            )
            or self.range_pct < 0
        ):
            raise ValueError(
                "Invalid previous-session range percentage."
            )

        if (
            not _finite(
                self.body_pct
            )
            or self.body_pct < 0
        ):
            raise ValueError(
                "Invalid previous-session body percentage."
            )

        direction = _norm(
            self.direction
        )

        if direction not in DIRECTIONS:
            raise ValueError(
                "Invalid previous-session direction."
            )

        if (
            not _finite(
                self.close_location
            )
            or not 0 <= self.close_location <= 1
        ):
            raise ValueError(
                "Close location must be between zero and one."
            )

        day_type = _norm(
            self.day_type
        )

        if day_type not in PREVIOUS_DAY_TYPES:
            raise ValueError(
                "Invalid previous-session day type."
            )

        if self.atr14 is not None:
            if (
                not _finite(
                    self.atr14
                )
                or self.atr14 <= 0
            ):
                raise ValueError(
                    "ATR14 must be positive when available."
                )

        source = _text(
            self.source
        )

        if source is None:
            raise ValueError(
                "Previous-session source is required."
            )

        if not _aware(
            self.observed_at
        ):
            raise ValueError(
                "Previous-session observed_at must be timezone-aware."
            )

        if (
            _evidence_status(
                self.evidence_status
            )
            != "AVAILABLE"
        ):
            raise ValueError(
                "Concrete previous-session intelligence must be AVAILABLE."
            )

        if (
            self.schema_version
            != "previous_session_intelligence.v2"
        ):
            raise ValueError(
                "Invalid previous-session schema."
            )

        object.__setattr__(
            self,
            "market_symbol",
            market.symbol,
        )

        object.__setattr__(
            self,
            "direction",
            direction,
        )

        object.__setattr__(
            self,
            "day_type",
            day_type,
        )

        object.__setattr__(
            self,
            "source",
            source,
        )


@dataclass(frozen=True, slots=True)
class GapContextV2:
    previous_close: float
    session_open: float

    gap_points: float
    gap_pct: float
    atr_multiple: float | None

    direction: str

    observed_at: datetime
    schema_version: str = "gap_context.v2"

    def __post_init__(
        self,
    ) -> None:
        if (
            not _finite(
                self.previous_close
            )
            or self.previous_close <= 0
        ):
            raise ValueError(
                "Previous close must be positive."
            )

        if (
            not _finite(
                self.session_open
            )
            or self.session_open <= 0
        ):
            raise ValueError(
                "Session open must be positive."
            )

        expected_points = (
            self.session_open
            - self.previous_close
        )

        expected_pct = (
            expected_points
            / self.previous_close
            * 100
        )

        if (
            not _finite(
                self.gap_points
            )
            or not math.isclose(
                self.gap_points,
                expected_points,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
        ):
            raise ValueError(
                "Gap points mismatch."
            )

        if (
            not _finite(
                self.gap_pct
            )
            or not math.isclose(
                self.gap_pct,
                expected_pct,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
        ):
            raise ValueError(
                "Gap percentage mismatch."
            )

        if self.atr_multiple is not None:
            if not _finite(
                self.atr_multiple
            ):
                raise ValueError(
                    "ATR-normalized gap must be finite."
                )

        direction = _norm(
            self.direction
        )

        expected_direction = (
            "UP"
            if expected_points > 0
            else (
                "DOWN"
                if expected_points < 0
                else "FLAT"
            )
        )

        if direction != expected_direction:
            raise ValueError(
                "Gap direction mismatch."
            )

        if not _aware(
            self.observed_at
        ):
            raise ValueError(
                "Gap observed_at must be timezone-aware."
            )

        if (
            self.schema_version
            != "gap_context.v2"
        ):
            raise ValueError(
                "Invalid gap schema."
            )

        object.__setattr__(
            self,
            "direction",
            direction,
        )


@dataclass(frozen=True, slots=True)
class GlobalRiskContextV2:
    evidence_status: str
    sentiment: str
    confidence: float | None
    coverage: str | None

    source: str
    observed_at: datetime

    freshness_status: str = "UNKNOWN"
    schema_version: str = "global_risk_context.v2"

    def __post_init__(
        self,
    ) -> None:
        status = _evidence_status(
            self.evidence_status
        )

        sentiment = _norm(
            self.sentiment
        )

        if sentiment not in GLOBAL_RISK_SENTIMENTS:
            raise ValueError(
                "Invalid global-risk sentiment."
            )

        if self.confidence is not None:
            if (
                not _finite(
                    self.confidence
                )
                or not 0 <= self.confidence <= 1
            ):
                raise ValueError(
                    "Global-risk confidence must be between zero and one."
                )

        if (
            status == "AVAILABLE"
            and sentiment == "UNKNOWN"
        ):
            raise ValueError(
                "Available global-risk evidence cannot be UNKNOWN."
            )

        if _text(
            self.source
        ) is None:
            raise ValueError(
                "Global-risk source is required."
            )

        if not _aware(
            self.observed_at
        ):
            raise ValueError(
                "Global-risk observed_at must be timezone-aware."
            )

        if (
            self.schema_version
            != "global_risk_context.v2"
        ):
            raise ValueError(
                "Invalid global-risk schema."
            )

        object.__setattr__(
            self,
            "evidence_status",
            status,
        )

        object.__setattr__(
            self,
            "sentiment",
            sentiment,
        )


@dataclass(frozen=True, slots=True)
class VolatilityContextV2:
    evidence_status: str

    vix: float | None
    change_1d_pct: float | None
    percentile: float | None

    regime: str
    trend: str

    source: str
    observed_at: datetime

    schema_version: str = "volatility_context.v2"

    def __post_init__(
        self,
    ) -> None:
        status = _evidence_status(
            self.evidence_status
        )

        if status == "AVAILABLE":
            if (
                not _finite(
                    self.vix
                )
                or self.vix <= 0
            ):
                raise ValueError(
                    "Available VIX evidence requires a positive value."
                )

        for value in (
            self.change_1d_pct,
            self.percentile,
        ):
            if (
                value is not None
                and not _finite(
                    value
                )
            ):
                raise ValueError(
                    "Volatility numeric field must be finite."
                )

        if (
            self.percentile is not None
            and not 0 <= self.percentile <= 100
        ):
            raise ValueError(
                "Volatility percentile must be between zero and 100."
            )

        if _text(
            self.source
        ) is None:
            raise ValueError(
                "Volatility source is required."
            )

        if not _aware(
            self.observed_at
        ):
            raise ValueError(
                "Volatility observed_at must be timezone-aware."
            )

        if (
            self.schema_version
            != "volatility_context.v2"
        ):
            raise ValueError(
                "Invalid volatility schema."
            )

        object.__setattr__(
            self,
            "evidence_status",
            status,
        )

        object.__setattr__(
            self,
            "regime",
            _norm(
                self.regime
            ) or "UNKNOWN",
        )

        object.__setattr__(
            self,
            "trend",
            _norm(
                self.trend
            ) or "UNKNOWN",
        )


@dataclass(frozen=True, slots=True)
class InstitutionalCashFlowV2:
    evidence_status: str

    trade_date: str | None

    fii_cash_net: float | None
    dii_cash_net: float | None
    combined_net: float | None

    bias: str

    source: str
    observed_at: datetime

    schema_version: str = (
        "institutional_cash_flow.v2"
    )

    def __post_init__(
        self,
    ) -> None:
        status = _evidence_status(
            self.evidence_status
        )

        bias = _norm(
            self.bias
        )

        if bias not in FLOW_BIASES:
            raise ValueError(
                "Invalid institutional-flow bias."
            )

        values = (
            self.fii_cash_net,
            self.dii_cash_net,
            self.combined_net,
        )

        if status == "AVAILABLE":
            if not all(
                _finite(value)
                for value in values
            ):
                raise ValueError(
                    "Available institutional-flow evidence requires all cash-flow values."
                )

        if _text(
            self.source
        ) is None:
            raise ValueError(
                "Institutional-flow source is required."
            )

        if not _aware(
            self.observed_at
        ):
            raise ValueError(
                "Institutional-flow observed_at must be timezone-aware."
            )

        if (
            self.schema_version
            != "institutional_cash_flow.v2"
        ):
            raise ValueError(
                "Invalid institutional-flow schema."
            )

        object.__setattr__(
            self,
            "evidence_status",
            status,
        )

        object.__setattr__(
            self,
            "bias",
            bias,
        )


@dataclass(frozen=True, slots=True)
class EventRiskContextV2:
    evidence_status: str

    source_authoritative: bool
    provider_block_entries: bool
    hard_block_eligible: bool

    event_names: tuple[str, ...]
    threshold_minutes: int | None

    source: str
    observed_at: datetime

    schema_version: str = "event_risk_context.v2"

    def __post_init__(
        self,
    ) -> None:
        status = _evidence_status(
            self.evidence_status
        )

        if not isinstance(
            self.source_authoritative,
            bool,
        ):
            raise ValueError(
                "source_authoritative must be boolean."
            )

        if not isinstance(
            self.provider_block_entries,
            bool,
        ):
            raise ValueError(
                "provider_block_entries must be boolean."
            )

        if not isinstance(
            self.hard_block_eligible,
            bool,
        ):
            raise ValueError(
                "hard_block_eligible must be boolean."
            )

        expected_hard_block = (
            self.source_authoritative
            and self.provider_block_entries
            and status == "AVAILABLE"
        )

        if (
            self.hard_block_eligible
            is not expected_hard_block
        ):
            raise ValueError(
                "Event hard-block eligibility is inconsistent with source authority."
            )

        if (
            status == "UNVERIFIED"
            and self.source_authoritative
        ):
            raise ValueError(
                "UNVERIFIED event evidence cannot be authoritative."
            )

        if not isinstance(
            self.event_names,
            tuple,
        ):
            raise ValueError(
                "event_names must be a tuple."
            )

        if self.threshold_minutes is not None:
            if (
                not isinstance(
                    self.threshold_minutes,
                    int,
                )
                or isinstance(
                    self.threshold_minutes,
                    bool,
                )
                or self.threshold_minutes < 0
            ):
                raise ValueError(
                    "Invalid event threshold."
                )

        if _text(
            self.source
        ) is None:
            raise ValueError(
                "Event source is required."
            )

        if not _aware(
            self.observed_at
        ):
            raise ValueError(
                "Event observed_at must be timezone-aware."
            )

        if (
            self.schema_version
            != "event_risk_context.v2"
        ):
            raise ValueError(
                "Invalid event-risk schema."
            )

        object.__setattr__(
            self,
            "evidence_status",
            status,
        )


@dataclass(frozen=True, slots=True)
class PreMarketStateV2:
    market_symbol: str
    generated_at: datetime

    previous_session_status: str
    previous_session: PreviousSessionIntelligenceV2 | None

    gap: GapContextV2 | None
    global_risk: GlobalRiskContextV2
    volatility: VolatilityContextV2
    institutional_flow: InstitutionalCashFlowV2
    event_risk: EventRiskContextV2

    execution_mode: str = "PAPER"
    broker_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = "pre_market_state.v2"

    def __post_init__(
        self,
    ) -> None:
        market = get_target_market(
            self.market_symbol
        )

        if not _aware(
            self.generated_at
        ):
            raise ValueError(
                "Pre-market generated_at must be timezone-aware."
            )

        previous_status = _evidence_status(
            self.previous_session_status
        )

        if previous_status == "AVAILABLE":
            if self.previous_session is None:
                raise ValueError(
                    "Available previous-session status requires evidence."
                )

        if (
            previous_status != "AVAILABLE"
            and self.previous_session is not None
        ):
            raise ValueError(
                "Unavailable previous-session status cannot carry a snapshot."
            )

        if self.previous_session is not None:
            if (
                self.previous_session.market_symbol
                != market.symbol
            ):
                raise ValueError(
                    "Previous-session market mismatch."
                )

        if (
            self.gap is not None
            and self.previous_session is None
        ):
            raise ValueError(
                "Gap context requires previous-session evidence."
            )

        if self.execution_mode != "PAPER":
            raise ValueError(
                "Pre-market state is PAPER only."
            )

        if self.broker_submission is not False:
            raise ValueError(
                "Broker submission must remain false."
            )

        if self.live_execution_eligible is not False:
            raise ValueError(
                "Live execution must remain ineligible."
            )

        if (
            self.schema_version
            != "pre_market_state.v2"
        ):
            raise ValueError(
                "Invalid pre-market state schema."
            )

        object.__setattr__(
            self,
            "market_symbol",
            market.symbol,
        )

        object.__setattr__(
            self,
            "previous_session_status",
            previous_status,
        )
