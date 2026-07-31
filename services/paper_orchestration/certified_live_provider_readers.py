from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.paper_orchestration.certified_live_read_authorities import (
    CertifiedLiveAnalysisResultV1,
    CertifiedLiveDataResultV1,
)


QuoteReader = Callable[
    [str, str, str],
    Mapping[str, Any],
]


@dataclass(frozen=True, slots=True)
class CertifiedIndexMarketSpecV1:
    underlying_symbol: str
    exchange: str
    symboltoken: str
    option_exchange: str

    def __post_init__(self) -> None:
        symbol = str(
            self.underlying_symbol
        ).strip().upper()
        exchange = str(
            self.exchange
        ).strip().upper()
        symboltoken = str(
            self.symboltoken
        ).strip()
        option_exchange = str(
            self.option_exchange
        ).strip().upper()

        allowed = {
            (
                "NIFTY",
                "NSE",
                "99926000",
                "NFO",
            ),
            (
                "SENSEX",
                "BSE",
                "99919000",
                "BFO",
            ),
        }

        identity = (
            symbol,
            exchange,
            symboltoken,
            option_exchange,
        )

        if identity not in allowed:
            raise ValueError(
                "unsupported certified index market "
                "specification"
            )

        object.__setattr__(
            self,
            "underlying_symbol",
            symbol,
        )
        object.__setattr__(
            self,
            "exchange",
            exchange,
        )
        object.__setattr__(
            self,
            "symboltoken",
            symboltoken,
        )
        object.__setattr__(
            self,
            "option_exchange",
            option_exchange,
        )


NIFTY_MARKET_SPEC = CertifiedIndexMarketSpecV1(
    underlying_symbol="NIFTY",
    exchange="NSE",
    symboltoken="99926000",
    option_exchange="NFO",
)

SENSEX_MARKET_SPEC = CertifiedIndexMarketSpecV1(
    underlying_symbol="SENSEX",
    exchange="BSE",
    symboltoken="99919000",
    option_exchange="BFO",
)


def market_spec_for(
    underlying_symbol: str,
    exchange: str,
) -> CertifiedIndexMarketSpecV1:
    identity = (
        str(underlying_symbol).strip().upper(),
        str(exchange).strip().upper(),
    )

    if identity == ("NIFTY", "NSE"):
        return NIFTY_MARKET_SPEC

    if identity == ("SENSEX", "BSE"):
        return SENSEX_MARKET_SPEC

    raise ValueError(
        "certified live readers support only "
        "NIFTY/NSE and SENSEX/BSE"
    )


def _mapping(
    value: object,
    name: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(
            f"{name} must return a mapping"
        )

    return dict(value)


def _positive(
    value: object,
    name: str,
) -> float:
    if isinstance(value, bool):
        raise TypeError(
            f"{name} must be numeric"
        )

    if type(value) not in {
        int,
        float,
    }:
        raise TypeError(
            f"{name} must be numeric"
        )

    result = float(value)

    if result <= 0:
        raise ValueError(
            f"{name} must be greater than zero"
        )

    return result


def _aware(
    value: object,
    name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(
            f"{name} must be a datetime"
        )

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{name} must be timezone-aware"
        )

    return value


class CertifiedLiveProviderReaders:
    """Read-only adapters around live market pipelines.

    Quote acquisition occurs once at the composition boundary.
    The DATA authority reuses the certified observation stored in
    the cycle input instead of requesting a second quote.
    """

    def __init__(
        self,
        *,
        quote_reader: QuoteReader,
        analysis_pipeline: object,
        option_decision_pipeline: object,
        available_capital: float,
        risk_percent: float = 1.0,
        maximum_capital_usage_percent: float = 100.0,
    ) -> None:
        if not callable(quote_reader):
            raise TypeError(
                "quote_reader must be callable"
            )

        if not callable(
            getattr(
                analysis_pipeline,
                "analyse",
                None,
            )
        ):
            raise TypeError(
                "analysis_pipeline must expose analyse()"
            )

        if not callable(
            getattr(
                option_decision_pipeline,
                "analyse",
                None,
            )
        ):
            raise TypeError(
                "option_decision_pipeline must expose analyse()"
            )

        self.quote_reader = quote_reader
        self.analysis_pipeline = analysis_pipeline
        self.option_decision_pipeline = (
            option_decision_pipeline
        )

        self.available_capital = _positive(
            available_capital,
            "available_capital",
        )
        self.risk_percent = _positive(
            risk_percent,
            "risk_percent",
        )
        self.maximum_capital_usage_percent = _positive(
            maximum_capital_usage_percent,
            "maximum_capital_usage_percent",
        )

    def read_data(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
    ) -> Mapping[str, Any]:
        if (
            type(cycle_input)
            is not PaperOrchestrationCycleInputV1
        ):
            raise TypeError(
                "cycle_input must be exact "
                "PaperOrchestrationCycleInputV1"
            )

        spec = market_spec_for(
            cycle_input.underlying_symbol,
            cycle_input.exchange,
        )

        spot_price = cycle_input.metadata.get(
            "spot_price"
        )

        if spot_price is None:
            raise ValueError(
                "cycle input metadata must contain "
                "the certified spot_price"
            )

        market_timestamp = _aware(
            cycle_input.market_timestamp,
            "market_timestamp",
        )
        received_at = _aware(
            cycle_input.received_at,
            "received_at",
        )

        if received_at < market_timestamp:
            raise ValueError(
                "received_at cannot precede "
                "market_timestamp"
            )

        return {
            "symboltoken": spec.symboltoken,
            "market_timestamp": market_timestamp,
            "received_at": received_at,
            "spot_price": _positive(
                spot_price,
                "spot_price",
            ),
            "payload": {
                "observation_source": (
                    "CERTIFIED_CYCLE_INPUT"
                ),
                "timestamp_source": (
                    cycle_input.metadata.get(
                        "timestamp_source"
                    )
                ),
                "market_spec": {
                    "underlying_symbol": (
                        spec.underlying_symbol
                    ),
                    "exchange": spec.exchange,
                    "symboltoken": (
                        spec.symboltoken
                    ),
                    "option_exchange": (
                        spec.option_exchange
                    ),
                },
                "execution_mode": "PAPER",
                "live_execution_eligible": False,
                "broker_order_submission": False,
            },
        }

    def read_analysis(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
        data_result: CertifiedLiveDataResultV1,
    ) -> Mapping[str, Any]:
        if (
            type(cycle_input)
            is not PaperOrchestrationCycleInputV1
        ):
            raise TypeError(
                "cycle_input must be exact "
                "PaperOrchestrationCycleInputV1"
            )

        if (
            type(data_result)
            is not CertifiedLiveDataResultV1
        ):
            raise TypeError(
                "data_result must be exact "
                "CertifiedLiveDataResultV1"
            )

        if (
            data_result.market_timestamp
            != cycle_input.market_timestamp
        ):
            raise ValueError(
                "analysis data timestamp does not match "
                "the certified cycle observation"
            )

        result = _mapping(
            self.analysis_pipeline.analyse(
                exchange=data_result.exchange,
                symboltoken=data_result.symboltoken,
                end_time=data_result.market_timestamp,
            ),
            "LiveAnalysisPipeline.analyse",
        )

        return {
            "analysis": result,
            "warnings": (),
            "blockers": (),
        }

    def read_opportunity(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
        analysis_result: CertifiedLiveAnalysisResultV1,
        session_result: object,
    ) -> Mapping[str, Any]:
        if (
            type(cycle_input)
            is not PaperOrchestrationCycleInputV1
        ):
            raise TypeError(
                "cycle_input must be exact "
                "PaperOrchestrationCycleInputV1"
            )

        if (
            type(analysis_result)
            is not CertifiedLiveAnalysisResultV1
        ):
            raise TypeError(
                "analysis_result must be exact "
                "CertifiedLiveAnalysisResultV1"
            )

        spec = market_spec_for(
            cycle_input.underlying_symbol,
            cycle_input.exchange,
        )

        spot_price = analysis_result.analysis.get(
            "spot_price"
        )

        if spot_price is None:
            spot_price = analysis_result.analysis.get(
                "ltp"
            )

        if spot_price is None:
            spot_price = cycle_input.metadata.get(
                "spot_price"
            )

        if spot_price is None:
            raise ValueError(
                "analysis result or cycle input must "
                "expose spot_price or ltp"
            )

        raw = _mapping(
            self.option_decision_pipeline.analyse(
                exchange=spec.exchange,
                symboltoken=spec.symboltoken,
                underlying=spec.underlying_symbol,
                spot_price=_positive(
                    spot_price,
                    "spot_price",
                ),
                option_exchange=spec.option_exchange,
                end_time=cycle_input.market_timestamp,
                capital=self.available_capital,
                risk_percent=self.risk_percent,
                maximum_capital_usage_percent=(
                    self.maximum_capital_usage_percent
                ),
                enforce_market_session=True,
                session_now=(
                    cycle_input.market_timestamp
                ),
            ),
            "LiveOptionDecisionPipeline.analyse",
        )

        decision = str(
            raw.get("decision", "")
        ).strip().upper()

        blockers = tuple(
            str(item).strip()
            for item in raw.get("blockers", ())
            if str(item).strip()
        )

        warnings = tuple(
            str(item).strip()
            for item in raw.get("warnings", ())
            if str(item).strip()
        )

        if decision in {
            "BUY",
            "TRADE",
            "TRADE_READY",
            "READY",
        }:
            status = "READY"

        elif decision in {
            "CONFLICTING",
            "MIXED",
        }:
            status = "CONFLICTING"
            blockers = blockers or (
                "CONFLICTING_SIGNALS",
            )

        elif decision in {
            "FAILED",
            "ERROR",
        }:
            status = "FAILED"
            blockers = blockers or (
                "UPSTREAM_FAILURE",
            )

        elif blockers:
            status = "BLOCKED"

        else:
            status = "NO_ACTION"
            decision = decision or "NO_TRADE"

        return {
            "opportunity_status": status,
            "decision": decision,
            "evidence": {
                "live_option_decision": raw,
                "analysis_observation_id": (
                    analysis_result.observation_id
                ),
                "certified_market_timestamp": (
                    cycle_input.market_timestamp.isoformat()
                ),
                "execution_mode": "PAPER",
                "live_execution_eligible": False,
                "broker_order_submission": False,
            },
            "blockers": blockers,
            "warnings": warnings,
        }