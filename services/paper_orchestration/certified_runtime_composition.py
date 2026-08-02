from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from zoneinfo import ZoneInfo

import config

from services.broker.shared_client import get_market_client
from services.contracts.certified_live_captured_evidence_v1 import (
    CertifiedLiveCapturedEvidenceV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)
from services.contracts.paper_market_observation_v1 import (
    PaperMarketObservationV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.contracts.paper_trade_lifecycle_policy_v1 import (
    PaperTradeLifecyclePolicyV1,
)
from services.live_analysis_pipeline import LiveAnalysisPipeline
from services.live_option_decision_pipeline import (
    LiveOptionDecisionPipeline,
)
from services.market.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
)
from services.market_session.validator import (
    validate_session_timestamp,
)
from services.paper_orchestration.certified_cycle_input_factory import (
    build_certified_cycle_input,
)
from services.paper_orchestration.certified_dashboard_composition import (
    build_certified_dashboard_publication,
)
from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
    market_spec_for,
)
from services.paper_orchestration.certified_live_read_authorities import (
    CertifiedLiveAnalysisAuthority,
    CertifiedLiveDataAuthority,
    CertifiedLiveOpportunityAuthority,
    CertifiedSessionAuthority,
)
from services.paper_orchestration.certified_operator_controls import (
    CertifiedOperatorControls,
    ControlledOpportunityInputFactory,
)
from services.paper_orchestration.certified_new_entry_input_factory import (
    CertifiedNewEntryInputFactory,
)
from services.paper_orchestration.certified_p6_input_factory import (
    CertifiedP6InputBundleV1,
    CertifiedP6InputFactory,
)
from services.paper_orchestration.certified_persistence_composition import (
    build_certified_coordinators,
    build_certified_persistence_paths,
)
from services.paper_orchestration.certified_runtime_launcher import (
    CertifiedLauncherCompositionV1,
)
from services.paper_orchestration.certified_runtime_logging import (
    CertifiedJsonLineLogger,
)
from services.paper_orchestration.certified_runtime_safety import (
    CertifiedPaperRuntimeSafetyConfigV1,
    validate_no_broker_submission_guard,
    validate_repository_paper_safety,
    validate_runtime_paths,
)
from services.paper_orchestration.complete_cycle_execution_context import (
    CompleteCycleAuthoritySetV1,
)
from services.paper_orchestration.complete_cycle_executor import (
    CompletePaperOrchestrationCycleExecutor,
)
from services.paper_orchestration.continuous_runtime_adapter import (
    ContinuousPaperOrchestrationRuntimeAdapter,
    ContinuousPaperOrchestrationRuntimeConfigV1,
)
from services.paper_orchestration.existing_position_monitoring_cycle_executor import (
    ExistingPositionMonitoringCycleExecutor,
)
from services.paper_orchestration.existing_position_monitoring_executor import (
    ExistingPositionMonitoringExecutor,
)
from services.paper_orchestration.new_entry_paper_lifecycle_executor import (
    NewEntryPaperLifecycleExecutor,
)
from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import (
    PaperPortfolioLifecycleCoordinator,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio_repository import (
    PaperPortfolioRepository,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from services.paper_trading.paper_trade_replay_coordinator import (
    PaperTradeReplayCoordinator,
)
from services.paper_trade_repository import PaperTradeRepository


IST = ZoneInfo("Asia/Kolkata")

Clock = Callable[[], datetime]
QuoteReader = Callable[[str, str, str], Mapping[str, Any]]


def _aware_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")

    return value


def _positive_float(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be numeric") from exc

    if result <= 0:
        raise ValueError(f"{name} must be greater than zero")

    return result


def _extract_spot_price(raw: Mapping[str, Any]) -> float:
    value = raw.get(
        "spot_price",
        raw.get(
            "ltp",
            raw.get("last_price"),
        ),
    )

    return _positive_float(value, "spot_price")


def _provider_ltp_reader(
    exchange: str,
    symboltoken: str,
    underlying: str,
) -> Mapping[str, Any]:
    client = get_market_client()

    response = client.get_ltp(
        exchange=exchange,
        tradingsymbol=underlying,
        symboltoken=symboltoken,
    )

    if not isinstance(response, Mapping):
        raise TypeError("market client must return a mapping")

    data = response.get("data")
    if not isinstance(data, Mapping):
        raise ValueError(
            "market client response must contain a data mapping"
        )

    spot_price = _positive_float(
        data.get(
            "ltp",
            data.get(
                "last_price",
                data.get("close"),
            ),
        ),
        "ltp",
    )

    received_at = _aware_now().astimezone(IST)

    return {
        "spot_price": spot_price,
        "ltp": spot_price,
        "market_timestamp": received_at,
        "received_at": received_at,
        "timestamp_source": "LOCAL_RECEIPT_TIME",
        "provider_response": dict(response),
    }


def capture_certified_live_evidence(
    *,
    cycle_input: PaperOrchestrationCycleInputV1,
    data_service: LiveMultiTimeframeData,
    option_decision_pipeline: LiveOptionDecisionPipeline,
) -> CertifiedLiveCapturedEvidenceV1:
    """Capture one certified market's read-only inputs for later reuse."""
    if type(cycle_input) is not PaperOrchestrationCycleInputV1:
        raise TypeError("cycle_input must be exact PaperOrchestrationCycleInputV1")
    spec = market_spec_for(cycle_input.underlying_symbol, cycle_input.exchange)
    if not callable(getattr(data_service, "fetch_all_with_capture", None)):
        raise TypeError("data_service must expose fetch_all_with_capture()")
    if not callable(getattr(option_decision_pipeline, "capture_option_inputs", None)):
        raise TypeError("option_decision_pipeline must expose capture_option_inputs()")
    spot_price = _extract_spot_price(cycle_input.metadata)
    market_timestamp = _aware_datetime(cycle_input.market_timestamp, "market_timestamp")
    evaluated_at = _aware_datetime(cycle_input.received_at, "received_at")
    payload = cycle_input.metadata.get("captured_spot_payload")
    if not isinstance(payload, Mapping):
        payload = {"spot_price": spot_price, "timestamp_source": cycle_input.metadata.get("timestamp_source")}
    captured = data_service.fetch_all_with_capture(spec.exchange, spec.symboltoken, end_time=market_timestamp)
    if not isinstance(captured, Mapping):
        raise TypeError("fetch_all_with_capture must return a mapping")
    rows = captured.get("rows_by_timeframe", {})
    cache_metadata = captured.get("cache_metadata", {})
    if not isinstance(rows, Mapping) or not isinstance(cache_metadata, Mapping):
        raise TypeError("invalid candle capture result")
    candle_blockers = tuple(
        f"CANDLE_CAPTURE_{timeframe.upper()}_{str(info.get('error')).upper()}"
        for timeframe, info in cache_metadata.items()
        if isinstance(info, Mapping) and not info.get("captured", False)
    )
    option_capture = option_decision_pipeline.capture_option_inputs(
        underlying=spec.underlying_symbol,
        spot_price=spot_price,
        option_exchange=spec.option_exchange,
        provider_timestamp=market_timestamp,
        evaluated_at=evaluated_at,
    )
    return CertifiedLiveCapturedEvidenceV1(
        underlying_symbol=spec.underlying_symbol,
        spot_exchange=spec.exchange,
        spot_token=spec.symboltoken,
        option_exchange=spec.option_exchange,
        spot_payload=payload,
        candle_rows_by_timeframe={key: tuple(value) for key, value in rows.items()},
        option_contracts=option_capture.contracts,
        provider_timestamp=market_timestamp,
        evaluated_at=evaluated_at,
        provider_blockers=candle_blockers + option_capture.blockers,
        provider_warnings=option_capture.warnings,
        cache_metadata={"candles": cache_metadata, "options": option_capture.metadata},
    )


@dataclass(frozen=True, slots=True)
class CertifiedRuntimeCompositionSettingsV1:
    data_root: Path = Path(
        "data/paper_trading/certified_runtime"
    )
    log_path: Path = Path(
        "data/paper_trading/certified_runtime/runtime.jsonl"
    )
    portfolio_id: str = "certified-paper-portfolio"
    available_capital: float = 10000.0
    interval_seconds: float = 60.0
    primary_symbol: str = "NIFTY"
    primary_exchange: str = "NSE"
    observe_only: bool = True
    emergency_halt: bool = False
    automated_paper: bool = False
    automated_authorities: object | None = None
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = (
        "certified_runtime_composition_settings.v1"
    )

    def __post_init__(self) -> None:
        data_root = Path(self.data_root)
        log_path = Path(self.log_path)

        object.__setattr__(self, "data_root", data_root)
        object.__setattr__(self, "log_path", log_path)

        if (
            type(self.portfolio_id) is not str
            or not self.portfolio_id.strip()
        ):
            raise ValueError(
                "portfolio_id must be a non-empty string"
            )

        object.__setattr__(
            self,
            "portfolio_id",
            self.portfolio_id.strip(),
        )

        available_capital = _positive_float(
            self.available_capital,
            "available_capital",
        )
        interval_seconds = _positive_float(
            self.interval_seconds,
            "interval_seconds",
        )

        object.__setattr__(
            self,
            "available_capital",
            available_capital,
        )
        object.__setattr__(
            self,
            "interval_seconds",
            interval_seconds,
        )

        market_spec_for(
            self.primary_symbol,
            self.primary_exchange,
        )

        if type(self.observe_only) is not bool:
            raise TypeError("observe_only")
        if type(self.emergency_halt) is not bool:
            raise TypeError("emergency_halt")
        if type(self.automated_paper) is not bool:
            raise TypeError("automated_paper")
        if self.automated_paper:
            if self.observe_only:
                raise ValueError("automated PAPER cannot be observe-only")
            if type(self.automated_authorities) is not AutomatedPaperAuthorityBundleV1:
                raise TypeError("automated_authorities")
        elif self.observe_only is not True:
            raise ValueError("certified composition must start observe-only")
        elif self.automated_authorities is not None:
            raise ValueError("automated authorities require automated PAPER mode")

        if self.execution_mode != "PAPER":
            raise ValueError(
                "execution_mode must be PAPER"
            )

        if self.live_execution_eligible:
            raise ValueError(
                "live execution is not eligible"
            )

        if self.schema_version != (
            "certified_runtime_composition_settings.v1"
        ):
            raise ValueError("unsupported schema_version")


@dataclass(frozen=True, slots=True)
class AutomatedPaperAuthorityBundleV1:
    """Exact, PAPER-only factories supplied by the existing P6 and P7/P8 layers."""

    p6_input_factory: CertifiedP6InputFactory
    new_entry_input_factory: CertifiedNewEntryInputFactory
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        if type(self.p6_input_factory) is not CertifiedP6InputFactory:
            raise TypeError("p6_input_factory")
        if type(self.new_entry_input_factory) is not CertifiedNewEntryInputFactory:
            raise TypeError("new_entry_input_factory")
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.broker_order_submission:
            raise ValueError("broker order submission must remain disabled")


def _p6_bundle_from_opportunity(
    cycle_input: object,
    analysis_result: object,
    opportunity_result: object,
) -> CertifiedP6InputBundleV1:
    """Consume only a real, upstream-certified P6 bundle; never invent one."""
    evidence = getattr(opportunity_result, "evidence", None)
    if not isinstance(evidence, Mapping):
        raise TypeError("opportunity result must carry P6 evidence")
    bundle = evidence.get("certified_p6_input_bundle")
    if type(bundle) is not CertifiedP6InputBundleV1:
        raise TypeError(
            "opportunity evidence must contain exact "
            "CertifiedP6InputBundleV1"
        )
    return bundle


def build_default_automated_paper_authorities(
    *,
    portfolio_id: str,
    available_capital: float,
) -> AutomatedPaperAuthorityBundleV1:
    """Compose the repository's typed P6 and PAPER lifecycle factories.

    P6 inputs are accepted only when the live opportunity authority has
    already supplied an exact certified bundle.  This is deliberately not a
    mapping adapter and does not fabricate a trade plan or signal.
    """
    capital = _positive_float(available_capital, "available_capital")

    def portfolio_policy(
        cycle_input,
        integrated_trade_plan_result,
    ) -> PaperPortfolioPolicyV1:
        return PaperPortfolioPolicyV1(
            portfolio_policy_id=(
                f"certified-paper-portfolio-policy:{cycle_input.trading_day_id}"
            ),
            policy_timestamp=cycle_input.cycle_requested_at,
            maximum_concurrent_trades=3,
            maximum_total_deployed_capital=capital,
            maximum_total_portfolio_risk_amount=capital * 0.10,
            maximum_daily_loss_amount=capital * 0.02,
            maximum_daily_drawdown_amount=capital * 0.03,
            maximum_instrument_risk_fraction=0.75,
            maximum_direction_risk_fraction=0.75,
            maximum_correlated_index_risk_fraction=0.60,
            maximum_expiry_risk_fraction=0.60,
            minimum_available_cash_reserve=0.0,
            metadata={"authority": "DEFAULT_AUTOMATED_PAPER"},
        )

    def lifecycle_policy(
        cycle_input,
        integrated_trade_plan_result,
    ) -> PaperTradeLifecyclePolicyV1:
        timestamp = cycle_input.cycle_requested_at
        return PaperTradeLifecyclePolicyV1(
            lifecycle_policy_id=(
                f"certified-paper-lifecycle-policy:{cycle_input.trading_day_id}"
            ),
            policy_timestamp=timestamp,
            policy_source="DEFAULT_AUTOMATED_PAPER",
            entry_timeout_seconds=300,
            maximum_observation_age_seconds=120,
            maximum_holding_seconds=21600,
            source_timestamps={"cycle_requested_at": timestamp},
        )

    def observation(
        cycle_input,
        integrated_trade_plan_result,
    ) -> PaperMarketObservationV1:
        selection = integrated_trade_plan_result.option_contract_selection_result
        candidate = selection.selected_contract
        if candidate is None:
            raise ValueError("READY P6 plan must select an option contract")
        contract = candidate.contract
        timestamp = cycle_input.cycle_requested_at
        spot_price = _extract_spot_price(cycle_input.metadata)
        option_price = contract.last_price
        if option_price is None:
            raise ValueError("selected option contract must contain last_price")
        return PaperMarketObservationV1(
            observation_id=f"{cycle_input.cycle_id}:entry-observation",
            trade_plan_id=integrated_trade_plan_result.capital_quantity_result.trade_plan_id,
            integrated_trade_plan_result_id=integrated_trade_plan_result.integration_id,
            selected_option_contract_id=contract.contract_id,
            observed_at=timestamp,
            received_at=timestamp,
            market_session_date=timestamp.astimezone(IST).date(),
            underlying_symbol=cycle_input.underlying_symbol,
            underlying_last_price=spot_price,
            option_symbol=contract.trading_symbol,
            option_last_price=option_price,
            market=cycle_input.underlying_symbol,
            exchange=cycle_input.exchange,
            session_state="OPEN",
            is_market_open=True,
            is_expiry_session=False,
            data_quality_status="FRESH",
            source="CERTIFIED_CYCLE_INPUT_AND_P6",
            bid_price=contract.bid_price,
            ask_price=contract.ask_price,
            source_timestamps={"cycle_requested_at": timestamp},
        )

    return AutomatedPaperAuthorityBundleV1(
        p6_input_factory=CertifiedP6InputFactory(
            typed_input_builder=_p6_bundle_from_opportunity,
        ),
        new_entry_input_factory=CertifiedNewEntryInputFactory(
            portfolio_id=portfolio_id,
            starting_capital=capital,
            portfolio_policy_provider=portfolio_policy,
            lifecycle_policy_provider=lifecycle_policy,
            observation_provider=observation,
        ),
    )


@dataclass(frozen=True, slots=True)
class CertifiedRuntimeProviderBundleV1:
    quote_reader: QuoteReader
    analysis_pipeline: object
    option_decision_pipeline: object
    candidate_reader: Callable[..., object] | None = None
    clock: Clock = _aware_now
    schema_version: str = (
        "certified_runtime_provider_bundle.v1"
    )

    def __post_init__(self) -> None:
        if not callable(self.quote_reader):
            raise TypeError("quote_reader must be callable")

        if not callable(self.clock):
            raise TypeError("clock must be callable")

        if not callable(
            getattr(
                self.analysis_pipeline,
                "analyse",
                None,
            )
        ):
            raise TypeError(
                "analysis_pipeline must expose analyse()"
            )

        if not callable(
            getattr(
                self.option_decision_pipeline,
                "analyse",
                None,
            )
        ):
            raise TypeError(
                "option_decision_pipeline must expose analyse()"
            )
        if self.candidate_reader is not None and not callable(self.candidate_reader):
            raise TypeError("candidate_reader")

        if self.schema_version != (
            "certified_runtime_provider_bundle.v1"
        ):
            raise ValueError("unsupported schema_version")


class CertifiedCycleSource:
    def __init__(
        self,
        *,
        readers: CertifiedLiveProviderReaders,
        settings: CertifiedRuntimeCompositionSettingsV1,
        clock: Clock,
    ) -> None:
        if (
            type(settings)
            is not CertifiedRuntimeCompositionSettingsV1
        ):
            raise TypeError(
                "settings must be exact "
                "CertifiedRuntimeCompositionSettingsV1"
            )

        if not callable(clock):
            raise TypeError("clock must be callable")

        self.readers = readers
        self.settings = settings
        self.clock = clock
        self._lock = RLock()
        self._sequence = 0

    def _next_sequence(self) -> int:
        with self._lock:
            self._sequence += 1
            return self._sequence

    def __call__(self, cycle_kind: str):
        kind = str(cycle_kind).strip().upper()

        if kind not in {
            "OPPORTUNITY",
            "MONITORING",
        }:
            raise ValueError(
                "cycle_kind must be OPPORTUNITY or MONITORING"
            )

        sequence = self._next_sequence()

        policy_timestamp = _aware_datetime(
            self.clock(),
            "clock result",
        )

        spec = market_spec_for(
            self.settings.primary_symbol,
            self.settings.primary_exchange,
        )

        raw = self.readers.quote_reader(
            spec.exchange,
            spec.symboltoken,
            spec.underlying_symbol,
        )

        if not isinstance(raw, Mapping):
            raise TypeError(
                "quote_reader must return a mapping"
            )

        raw_mapping = dict(raw)

        market_timestamp = _aware_datetime(
            raw_mapping.get("market_timestamp"),
            "market_timestamp",
        )
        received_at = _aware_datetime(
            raw_mapping.get("received_at"),
            "received_at",
        )

        if received_at < market_timestamp:
            raise ValueError(
                "received_at cannot precede market_timestamp"
            )

        cycle_requested_at = _aware_datetime(
            self.clock(),
            "clock result",
        )

        if cycle_requested_at < received_at:
            cycle_requested_at = received_at

        spot_price = _extract_spot_price(raw_mapping)

        session = validate_session_timestamp(
            symbol=spec.underlying_symbol,
            exchange=spec.exchange,
            market_timestamp=market_timestamp,
            evaluated_at=received_at,
            validation_mode="LENIENT_ANALYSIS",
            id_factory=lambda: (
                f"certified-session-"
                f"{kind.lower()}-"
                f"{sequence}"
            ),
        )

        observation_id = (
            f"certified-"
            f"{kind.lower()}-"
            f"{spec.underlying_symbol.lower()}-"
            f"{market_timestamp.isoformat()}-"
            f"{sequence}"
        )

        policy = PaperOrchestrationPolicyV1(
            orchestration_policy_id=(
                "certified-paper-policy-"
                f"{policy_timestamp.astimezone(IST).date()}"
            ),
            policy_timestamp=policy_timestamp,
            observation_frequency_seconds=(
                self.settings.interval_seconds
            ),
            emergency_paper_halt=False,
            metadata={
                "composition": "batch8",
                "default_observe_only": True,
            },
        )

        return build_certified_cycle_input(
            cycle_kind=kind,
            observation_id=observation_id,
            orchestration_policy=policy,
            underlying_symbol=spec.underlying_symbol,
            exchange=spec.exchange,
            market_timestamp=market_timestamp,
            received_at=received_at,
            cycle_requested_at=cycle_requested_at,
            session_validation=session,
            metadata={
                "composition": "batch8",
                "sequence": sequence,
                "timestamp_source": raw_mapping.get(
                    "timestamp_source"
                ),
                "spot_price": spot_price,
                "captured_spot_payload": {
                    "spot_price": spot_price,
                    "timestamp_source": raw_mapping.get("timestamp_source"),
                },
                "execution_mode": "PAPER",
            },
        )


def _observe_only_p6_input_factory(
    *args: object,
    **kwargs: object,
):
    raise RuntimeError(
        "P6 planning is disabled by the "
        "Batch 8 observe-only composition"
    )


def _observe_only_new_entry_input_factory(
    *args: object,
    **kwargs: object,
):
    raise RuntimeError(
        "new PAPER entries are disabled by the "
        "Batch 8 observe-only composition"
    )


def _no_active_position_monitoring_input(
    *args: object,
    **kwargs: object,
):
    raise RuntimeError(
        "no active certified P7 position is available "
        "for monitoring"
    )


def _recovery_success_empty() -> dict[str, object]:
    return {
        "success": True,
        "status": "RECOVERED",
        "target_count": 0,
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
    }


def build_default_runtime_providers(
) -> CertifiedRuntimeProviderBundleV1:
    shared_client = get_market_client()

    data_service = LiveMultiTimeframeData(
        client=shared_client,
        cache_enabled=True,
    )

    analysis_pipeline = LiveAnalysisPipeline(
        data_service=data_service,
    )

    option_pipeline = LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        market_client=shared_client,
        persist_audit=False,
    )

    return CertifiedRuntimeProviderBundleV1(
        quote_reader=_provider_ltp_reader,
        analysis_pipeline=analysis_pipeline,
        option_decision_pipeline=option_pipeline,
    )


def build_certified_launcher(
    *,
    settings: (
        CertifiedRuntimeCompositionSettingsV1 | None
    ) = None,
    providers: (
        CertifiedRuntimeProviderBundleV1 | None
    ) = None,
    automated_paper: bool = False,
) -> CertifiedLauncherCompositionV1:
    value = (
        settings
        if settings is not None
        else (
            CertifiedRuntimeCompositionSettingsV1(
                observe_only=False,
                automated_paper=True,
                automated_authorities=(
                    build_default_automated_paper_authorities(
                        portfolio_id="certified-paper-portfolio",
                        available_capital=10000.0,
                    )
                ),
            )
            if automated_paper
            else CertifiedRuntimeCompositionSettingsV1()
        )
    )

    if (
        type(value)
        is not CertifiedRuntimeCompositionSettingsV1
    ):
        raise TypeError(
            "settings must be exact "
            "CertifiedRuntimeCompositionSettingsV1"
        )

    if type(automated_paper) is not bool:
        raise TypeError("automated_paper")

    if (
        settings is not None
        and automated_paper != value.automated_paper
    ):
        raise ValueError(
            "automated_paper must match the explicit composition settings"
        )

    validate_repository_paper_safety(
        broker=config.BROKER,
        enable_paper_trading=config.ENABLE_PAPER_TRADING,
        enable_live_trading=config.ENABLE_LIVE_TRADING,
    )
    if value.automated_paper:
        validate_no_broker_submission_guard(
            broker_order_submission=False,
        )

    validate_runtime_paths(
        journal_directory=value.data_root,
        log_directory=value.log_path.parent,
    )

    safety = CertifiedPaperRuntimeSafetyConfigV1(
        instruments=("NIFTY", "SENSEX"),
        interval_seconds=value.interval_seconds,
        observe_only=value.observe_only,
        emergency_halt=value.emergency_halt,
    )

    if safety.observe_only is not value.observe_only:
        raise ValueError(
            "operator control safety invariant failed"
        )

    provider_bundle = (
        providers
        if providers is not None
        else build_default_runtime_providers()
    )

    if (
        type(provider_bundle)
        is not CertifiedRuntimeProviderBundleV1
    ):
        raise TypeError(
            "providers must be exact "
            "CertifiedRuntimeProviderBundleV1"
        )

    clock = provider_bundle.clock

    data_service = getattr(provider_bundle.analysis_pipeline, "data_service", None)
    capture_reader = None
    if callable(getattr(data_service, "fetch_all_with_capture", None)) and callable(getattr(provider_bundle.option_decision_pipeline, "capture_option_inputs", None)):
        def capture_reader(cycle_input):
            return capture_certified_live_evidence(
                cycle_input=cycle_input,
                data_service=data_service,
                option_decision_pipeline=provider_bundle.option_decision_pipeline,
            )

    readers = CertifiedLiveProviderReaders(
        quote_reader=provider_bundle.quote_reader,
        analysis_pipeline=(
            provider_bundle.analysis_pipeline
        ),
        option_decision_pipeline=(
            provider_bundle.option_decision_pipeline
        ),
        available_capital=value.available_capital,
        candidate_reader=provider_bundle.candidate_reader,
        capture_reader=capture_reader,
    )

    data_authority = CertifiedLiveDataAuthority(
        reader=readers.read_data,
    )
    session_authority = CertifiedSessionAuthority()
    analysis_authority = CertifiedLiveAnalysisAuthority(
        reader=readers.read_analysis,
    )
    opportunity_authority = (
        CertifiedLiveOpportunityAuthority(
            reader=readers.read_opportunity,
        )
    )

    trade_persistence = PaperTradePersistenceService(
        PaperTradeRepository(
            value.data_root / "p7_trades.json"
        )
    )

    portfolio_persistence = (
        PaperPortfolioPersistenceService(
            PaperPortfolioRepository(
                value.data_root / "p8_portfolios.json"
            )
        )
    )

    new_entry_executor = NewEntryPaperLifecycleExecutor(
        portfolio_persistence_service=(
            portfolio_persistence
        ),
        trade_persistence_service=trade_persistence,
        broker_order_submission=False,
    )

    automated_authorities = value.automated_authorities
    authorities = CompleteCycleAuthoritySetV1(
        data_authority=data_authority,
        session_authority=session_authority,
        analysis_authority=analysis_authority,
        opportunity_authority=opportunity_authority,
        p6_input_factory=(
            automated_authorities.p6_input_factory
            if value.automated_paper
            else _observe_only_p6_input_factory
        ),
        new_entry_input_factory=(
            automated_authorities.new_entry_input_factory
            if value.automated_paper
            else _observe_only_new_entry_input_factory
        ),
    )

    opportunity_executor = (
        CompletePaperOrchestrationCycleExecutor(
            authorities=authorities,
            new_entry_stage_authority=(
                new_entry_executor.execute
            ),
            clock=clock,
        )
    )

    monitoring_authority = (
        ExistingPositionMonitoringExecutor(
            trade_replay_coordinator=(
                PaperTradeReplayCoordinator(
                    trade_persistence
                )
            ),
            portfolio_lifecycle_coordinator=(
                PaperPortfolioLifecycleCoordinator(
                    portfolio_persistence
                )
            ),
        )
    )

    monitoring_executor = (
        ExistingPositionMonitoringCycleExecutor(
            monitoring_input_factory=(
                _no_active_position_monitoring_input
            ),
            monitoring_authority=(
                monitoring_authority.execute
            ),
            clock=clock,
        )
    )

    paths = build_certified_persistence_paths(
        value.data_root,
    )

    coordinators = build_certified_coordinators(
        opportunity_cycle_executor=(
            opportunity_executor
        ),
        monitoring_cycle_executor=monitoring_executor,
        clock=clock,
        paths=paths,
    )

    dashboard = build_certified_dashboard_publication(
        clock=clock,
    )

    controls = CertifiedOperatorControls(
        observe_only=value.observe_only,
        emergency_halt=value.emergency_halt,
    )

    cycle_source = CertifiedCycleSource(
        readers=readers,
        settings=value,
        clock=clock,
    )

    runtime = ContinuousPaperOrchestrationRuntimeAdapter(
        opportunity_coordinator=(
            coordinators.opportunity_coordinator
        ),
        opportunity_input_factory=(
            ControlledOpportunityInputFactory(
                delegate=lambda: cycle_source(
                    "OPPORTUNITY"
                ),
                controls=controls,
            )
        ),
        monitoring_coordinator=(
            coordinators.monitoring_coordinator
        ),
        monitoring_input_factory=lambda: cycle_source(
            "MONITORING"
        ),
        config=(
            ContinuousPaperOrchestrationRuntimeConfigV1(
                interval_seconds=value.interval_seconds,
            )
        ),
        startup_operation=_recovery_success_empty,
        dashboard_publication_producer=(
            dashboard.producer
        ),
        dashboard_publication_store=dashboard.store,
    )

    return CertifiedLauncherCompositionV1(
        runtime_adapter=runtime,
        controls=controls,
        logger=CertifiedJsonLineLogger(
            file_path=value.log_path,
        ),
        automated_paper=value.automated_paper,
    )


def build_automated_paper_launcher(
    *,
    settings: CertifiedRuntimeCompositionSettingsV1,
    providers: CertifiedRuntimeProviderBundleV1 | None = None,
) -> CertifiedLauncherCompositionV1:
    """Build the explicit automated PAPER composition, never a live one."""
    if type(settings) is not CertifiedRuntimeCompositionSettingsV1:
        raise TypeError("settings")
    if settings.automated_paper is not True:
        raise ValueError("settings must explicitly enable automated_paper")
    return build_certified_launcher(
        settings=settings,
        providers=providers,
        automated_paper=True,
    )
