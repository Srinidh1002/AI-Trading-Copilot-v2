from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from inspect import signature
from threading import RLock
from typing import Any, Protocol

from services.contracts.market_analysis_candidate_v1 import (
    MarketAnalysisCandidateV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.certified_live_captured_evidence_v1 import (
    CertifiedLiveCapturedEvidenceV1,
)
from services.market.live_multi_timeframe_data import normalize_angel_candles
from services.contracts.certified_shared_market_context_v1 import CertifiedSharedMarketContextV1
from services.paper_orchestration.certified_live_read_authorities import (
    CertifiedLiveAnalysisResultV1,
    CertifiedLiveDataResultV1,
)


QuoteReader = Callable[
    [str, str, str],
    Mapping[str, Any],
]
class CandidateReader(Protocol):
    def __call__(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
        data_result: CertifiedLiveDataResultV1,
        analysis: Mapping[str, Any],
        captured_evidence: CertifiedLiveCapturedEvidenceV1 | None,
        shared_context: CertifiedSharedMarketContextV1 | None,
        *,
        parent_cycle_id: str,
    ) -> MarketAnalysisCandidateV1: ...
CaptureReader = Callable[[PaperOrchestrationCycleInputV1], CertifiedLiveCapturedEvidenceV1]


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
        candidate_reader: CandidateReader | None = None,
        capture_reader: CaptureReader | None = None,
        india_vix_reader: object | None = None,
        substage_callback: Callable[[str], None] | None = None,
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

        if candidate_reader is not None and not callable(candidate_reader):
            raise TypeError("candidate_reader must be callable or None")
        if capture_reader is not None and not callable(capture_reader):
            raise TypeError("capture_reader must be callable or None")

        self.quote_reader = quote_reader
        self.analysis_pipeline = analysis_pipeline
        self.candidate_reader = candidate_reader
        self.capture_reader = capture_reader
        if india_vix_reader is not None and not callable(getattr(india_vix_reader, "capture", None)):
            raise TypeError("india_vix_reader must expose capture()")
        self.india_vix_reader = india_vix_reader
        if substage_callback is not None and not callable(substage_callback): raise TypeError("substage_callback")
        self.substage_callback = substage_callback
        self.india_vix_normalization_count = 0
        self._capture_lock = RLock()
        self._captures: dict[str, CertifiedLiveCapturedEvidenceV1] = {}
        self._shared_contexts: dict[str, CertifiedSharedMarketContextV1] = {}
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

    def _capture_for(self, cycle_input: PaperOrchestrationCycleInputV1, *, candle_cutoff: datetime | None = None) -> CertifiedLiveCapturedEvidenceV1 | None:
        if self.capture_reader is None:
            return None
        key = cycle_input.observation_id
        with self._capture_lock:
            existing = self._captures.get(key)
            if existing is not None:
                return existing
            if candle_cutoff is None:
                captured = self.capture_reader(cycle_input)
            else:
                try:
                    signature(self.capture_reader).bind(cycle_input, candle_cutoff=candle_cutoff)
                except TypeError:
                    captured = self.capture_reader(cycle_input)
                else:
                    captured = self.capture_reader(cycle_input, candle_cutoff=candle_cutoff)
            if type(captured) is not CertifiedLiveCapturedEvidenceV1:
                raise TypeError("capture_reader must return exact CertifiedLiveCapturedEvidenceV1")
            spec = market_spec_for(cycle_input.underlying_symbol, cycle_input.exchange)
            identity = (captured.underlying_symbol, captured.spot_exchange, captured.spot_token, captured.option_exchange)
            if identity != (spec.underlying_symbol, spec.exchange, spec.symboltoken, spec.option_exchange):
                raise ValueError("captured evidence identity does not match certified cycle")
            self._captures[key] = captured
            return captured

    @staticmethod
    def _candidate_with_capture(reader, cycle_input, data_result, analysis, captured, shared_context, *, parent_cycle_id):
        return reader(cycle_input, data_result, analysis, captured, shared_context, parent_cycle_id=parent_cycle_id)

    @staticmethod
    def _normalized_capture(cycle_input, captured, *, evaluated_at=None):
        from services.market.angel_live_observation_normalizer import normalize_angel_live_observation

        spec = market_spec_for(cycle_input.underlying_symbol, cycle_input.exchange)
        payload = dict(captured.spot_payload)
        if "data" not in payload:
            payload = {"data": {"ltp": payload.get("spot_price", payload.get("ltp")), "tradingsymbol": spec.underlying_symbol, "exchange": spec.exchange, "symboltoken": spec.symboltoken}}
        return normalize_angel_live_observation(
            spot_response=payload, candle_rows_by_timeframe=captured.candle_rows_by_timeframe,
            market_spec=spec, provider_timestamp=captured.provider_timestamp,
            evaluated_at=evaluated_at if evaluated_at is not None else captured.evaluated_at, blockers=captured.provider_blockers,
            warnings=captured.provider_warnings,
        )

    def prepare_shared_broader_context(self, nifty_cycle: PaperOrchestrationCycleInputV1, sensex_cycle: PaperOrchestrationCycleInputV1) -> CertifiedSharedMarketContextV1:
        """Capture each child once, then build one provider-free shared context."""
        from services.analysis.shared_broader_market_context import build_certified_shared_broader_context

        if (nifty_cycle.underlying_symbol, nifty_cycle.exchange) != ("NIFTY", "NSE") or (sensex_cycle.underlying_symbol, sensex_cycle.exchange) != ("SENSEX", "BSE"):
            raise ValueError("shared context identity")
        # The cross-market source is the final completed 5m candle, not the
        # sequential quote receipt.  One conservative cutoff keeps both
        # historical requests on the same completed exchange boundary.
        earliest = min(nifty_cycle.market_timestamp, sensex_cycle.market_timestamp)
        candle_cutoff = earliest - timedelta(minutes=earliest.minute % 5, seconds=earliest.second, microseconds=earliest.microsecond)
        nifty = self._capture_for(nifty_cycle, candle_cutoff=candle_cutoff)
        sensex = self._capture_for(sensex_cycle, candle_cutoff=candle_cutoff)
        if nifty is None or sensex is None:
            raise RuntimeError("shared broader context requires certified captures")
        vix_capture = self.india_vix_reader.capture(f"{nifty_cycle.observation_id}:{sensex_cycle.observation_id}") if self.india_vix_reader else None
        if self.substage_callback is not None: self.substage_callback("INDIA_VIX_CAPTURE_COMPLETE")
        if vix_capture is not None:
            self.india_vix_normalization_count += 1
        # Each provider receipt remains on its captured evidence.  The shared
        # cross-market calculation uses one boundary after every shared input
        # has been captured; otherwise a fresh later VIX looks future-dated.
        parent_evaluated_at = max(
            nifty.evaluated_at,
            sensex.evaluated_at,
            vix_capture.evaluated_at if vix_capture is not None else nifty.evaluated_at,
        )
        context = build_certified_shared_broader_context(
            nifty_observation=self._normalized_capture(nifty_cycle, nifty, evaluated_at=parent_evaluated_at),
            sensex_observation=self._normalized_capture(sensex_cycle, sensex, evaluated_at=parent_evaluated_at),
            evaluated_at=parent_evaluated_at,
            india_vix_capture=vix_capture,
            capture_diagnostics={
                "NIFTY": {"provider_timestamp": nifty.provider_timestamp, "received_at": nifty.evaluated_at, "cache_metadata": dict(nifty.cache_metadata), "shared_candle_cutoff": candle_cutoff},
                "SENSEX": {"provider_timestamp": sensex.provider_timestamp, "received_at": sensex.evaluated_at, "cache_metadata": dict(sensex.cache_metadata), "shared_candle_cutoff": candle_cutoff},
            },
        )
        if self.substage_callback is not None: self.substage_callback("SHARED_CONTEXT_BUILD_COMPLETE")
        with self._capture_lock:
            self._shared_contexts[nifty_cycle.observation_id] = context
            self._shared_contexts[sensex_cycle.observation_id] = context
        return context

    def shared_context_for(self, observation_id: str) -> CertifiedSharedMarketContextV1 | None:
        """Read-only evidence accessor for parent-only certification reports."""
        with self._capture_lock:
            return self._shared_contexts.get(observation_id)

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

        captured = self._capture_for(cycle_input)

        spot_price = (captured.spot_payload.get("spot_price", captured.spot_payload.get("ltp")) if captured is not None else cycle_input.metadata.get(
            "spot_price"
        ))

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
        *,
        parent_cycle_id: str,
    ) -> Mapping[str, Any]:
        if (
            type(cycle_input)
            is not PaperOrchestrationCycleInputV1
            ):
            raise TypeError(
                "cycle_input must be exact "
                "PaperOrchestrationCycleInputV1"
            )
        if type(parent_cycle_id) is not str or not parent_cycle_id.strip():
            raise ValueError("parent_cycle_id")

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

        captured = self._capture_for(cycle_input)
        captured_timeframes = None
        if captured is not None:
            captured_timeframes = {"dataframes": {key: normalize_angel_candles(value) for key, value in captured.candle_rows_by_timeframe.items()}, "rows_by_timeframe": captured.candle_rows_by_timeframe, "cache_metadata": captured.cache_metadata}
        kwargs = {"exchange": data_result.exchange, "symboltoken": data_result.symboltoken, "end_time": data_result.market_timestamp}
        if captured_timeframes is not None:
            kwargs["captured_timeframes"] = captured_timeframes
        result = _mapping(self.analysis_pipeline.analyse(**kwargs), "LiveAnalysisPipeline.analyse")

        candidate = None
        if self.candidate_reader is not None:
            candidate = self._candidate_with_capture(self.candidate_reader, cycle_input, data_result, result, captured, self._shared_contexts.get(cycle_input.observation_id), parent_cycle_id=parent_cycle_id)
            if type(candidate) is not MarketAnalysisCandidateV1:
                raise TypeError(
                    "candidate_reader must return exact "
                    "MarketAnalysisCandidateV1"
                )
            expected = (
                cycle_input.observation_id,
                cycle_input.underlying_symbol,
                cycle_input.exchange,
                data_result.symboltoken,
                cycle_input.market_timestamp,
            )
            actual = (
                candidate.observation_id,
                candidate.underlying_symbol,
                candidate.exchange,
                candidate.symboltoken,
                candidate.market_timestamp,
            )
            if actual != expected:
                raise ValueError(
                    "candidate identity does not match certified child cycle"
                )

        return {
            "analysis": result,
            "candidate": candidate,
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
        captured = self._capture_for(cycle_input)

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

        kwargs = dict(
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
            )
        if captured is not None:
            kwargs["captured_option_input"] = {"underlying": captured.underlying_symbol, "spot_price": _positive(spot_price, "spot_price"), "contracts": captured.option_contracts}
        raw = _mapping(self.option_decision_pipeline.analyse(**kwargs), "LiveOptionDecisionPipeline.analyse")

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
                "market_analysis_candidate": (
                    analysis_result.candidate
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
