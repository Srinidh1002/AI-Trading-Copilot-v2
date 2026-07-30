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
from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
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


def _positive_float(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(name)
    result = float(value)
    if result <= 0:
        raise ValueError(name)
    return result


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
        raise ValueError("market client response has no data mapping")
    ltp = _positive_float(data.get("ltp"), "ltp")
    received_at = _aware_now().astimezone(IST)
    return {
        "ltp": ltp,
        "market_timestamp": received_at,
        "received_at": received_at,
        "timestamp_source": "LOCAL_RECEIPT_TIME",
        "provider_response": response,
    }


@dataclass(frozen=True, slots=True)
class CertifiedRuntimeCompositionSettingsV1:
    data_root: Path = Path("data/paper_trading/certified_runtime")
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
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "certified_runtime_composition_settings.v1"

    def __post_init__(self) -> None:
        root = Path(self.data_root)
        log = Path(self.log_path)
        object.__setattr__(self, "data_root", root)
        object.__setattr__(self, "log_path", log)
        if type(self.portfolio_id) is not str or not self.portfolio_id.strip():
            raise ValueError("portfolio_id")
        _positive_float(self.available_capital, "available_capital")
        if float(self.interval_seconds) <= 0:
            raise ValueError(
                "interval_seconds must be greater than zero"
            )
        market_spec_for(self.primary_symbol, self.primary_exchange)
        if self.observe_only is not True:
            raise ValueError(
                "Batch 8 composition must start observe-only"
            )
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != (
            "certified_runtime_composition_settings.v1"
        ):
            raise ValueError("unsupported schema_version")


@dataclass(frozen=True, slots=True)
class CertifiedRuntimeProviderBundleV1:
    quote_reader: QuoteReader
    analysis_pipeline: object
    option_decision_pipeline: object
    clock: Clock = _aware_now
    schema_version: str = "certified_runtime_provider_bundle.v1"

    def __post_init__(self) -> None:
        if not callable(self.quote_reader):
            raise TypeError("quote_reader")
        if not callable(self.clock):
            raise TypeError("clock")
        if not callable(getattr(self.analysis_pipeline, "analyse", None)):
            raise TypeError("analysis_pipeline.analyse")
        if not callable(
            getattr(self.option_decision_pipeline, "analyse", None)
        ):
            raise TypeError("option_decision_pipeline.analyse")
        if self.schema_version != "certified_runtime_provider_bundle.v1":
            raise ValueError("unsupported schema_version")


class CertifiedCycleSource:
    def __init__(
        self,
        *,
        readers: CertifiedLiveProviderReaders,
        settings: CertifiedRuntimeCompositionSettingsV1,
        clock: Clock,
    ) -> None:
        self.readers = readers
        self.settings = settings
        self.clock = clock
        self._lock = RLock()
        self._sequence = 0

    def __call__(self, cycle_kind: str):
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
        now = self.clock()
        if not isinstance(now, datetime):
            raise TypeError("clock must return datetime")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return timezone-aware datetime")
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
            raise TypeError("quote_reader must return a mapping")
        market_timestamp = raw.get("market_timestamp")
        received_at = raw.get("received_at")
        if not isinstance(market_timestamp, datetime):
            raise TypeError("market_timestamp")
        if not isinstance(received_at, datetime):
            raise TypeError("received_at")
        session = validate_session_timestamp(
            symbol=spec.underlying_symbol,
            exchange=spec.exchange,
            market_timestamp=market_timestamp,
            evaluated_at=received_at,
            validation_mode="LENIENT_ANALYSIS",
            id_factory=lambda: (
                f"certified-session-{cycle_kind.lower()}-{sequence}"
            ),
        )
        observation_id = (
            f"certified-{cycle_kind.lower()}-"
            f"{spec.underlying_symbol.lower()}-"
            f"{market_timestamp.isoformat()}-{sequence}"
        )
        policy = PaperOrchestrationPolicyV1(
            orchestration_policy_id=(
                f"certified-paper-policy-{now.astimezone(IST).date()}"
            ),
            policy_timestamp=now,
            observation_frequency_seconds=(
                float(self.settings.interval_seconds)
            ),
            emergency_paper_halt=False,
            metadata={
                "composition": "batch8",
                "default_observe_only": True,
            },
        )
        return build_certified_cycle_input(
            cycle_kind=cycle_kind,
            observation_id=observation_id,
            orchestration_policy=policy,
            underlying_symbol=spec.underlying_symbol,
            exchange=spec.exchange,
            market_timestamp=market_timestamp,
            received_at=received_at,
            cycle_requested_at=now,
            session_validation=session,
            metadata={
                "composition": "batch8",
                "sequence": sequence,
                "timestamp_source": raw.get("timestamp_source"),
                "execution_mode": "PAPER",
                "live_execution_eligible": False,
                "broker_order_submission": False,
            },
        )


def _observe_only_p6_input_factory(*args, **kwargs):
    raise RuntimeError(
        "P6 planning is disabled by the Batch 8 observe-only composition"
    )


def _observe_only_new_entry_input_factory(*args, **kwargs):
    raise RuntimeError(
        "new PAPER entries are disabled by the Batch 8 composition"
    )


def _no_active_position_monitoring_input(*args, **kwargs):
    raise RuntimeError(
        "no active certified P7 position is available for monitoring"
    )


def _recovery_success_empty() -> dict[str, object]:
    return {
        "success": True,
        "status": "RECOVERED",
        "target_count": 0,
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
    }


def build_default_runtime_providers() -> CertifiedRuntimeProviderBundleV1:
    shared_client = get_market_client()
    data_service = LiveMultiTimeframeData(
        client=shared_client,
        cache_enabled=False,
    )
    analysis_pipeline = LiveAnalysisPipeline(data_service=data_service)
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
    settings: CertifiedRuntimeCompositionSettingsV1 | None = None,
    providers: CertifiedRuntimeProviderBundleV1 | None = None,
) -> CertifiedLauncherCompositionV1:
    value = settings or CertifiedRuntimeCompositionSettingsV1()
    if type(value) is not CertifiedRuntimeCompositionSettingsV1:
        raise TypeError("settings")
    validate_repository_paper_safety(
        broker=config.BROKER,
        enable_paper_trading=config.ENABLE_PAPER_TRADING,
        enable_live_trading=config.ENABLE_LIVE_TRADING,
    )
    validate_runtime_paths(
        journal_directory=value.data_root,
        log_directory=value.log_path.parent,
    )
    safety = CertifiedPaperRuntimeSafetyConfigV1(
        instruments=("NIFTY", "SENSEX"),
        interval_seconds=float(value.interval_seconds),
        observe_only=True,
        emergency_halt=value.emergency_halt,
    )
    if safety.observe_only is not True:
        raise ValueError("observe-only safety invariant failed")

    provider_bundle = providers or build_default_runtime_providers()
    if type(provider_bundle) is not CertifiedRuntimeProviderBundleV1:
        raise TypeError("providers")
    clock = provider_bundle.clock
    readers = CertifiedLiveProviderReaders(
        quote_reader=provider_bundle.quote_reader,
        analysis_pipeline=provider_bundle.analysis_pipeline,
        option_decision_pipeline=provider_bundle.option_decision_pipeline,
        available_capital=float(value.available_capital),
    )
    data_authority = CertifiedLiveDataAuthority(reader=readers.read_data)
    session_authority = CertifiedSessionAuthority()
    analysis_authority = CertifiedLiveAnalysisAuthority(
        reader=readers.read_analysis
    )
    opportunity_authority = CertifiedLiveOpportunityAuthority(
        reader=readers.read_opportunity
    )

    trade_persistence = PaperTradePersistenceService(
        PaperTradeRepository(value.data_root / "p7_trades.json")
    )
    portfolio_persistence = PaperPortfolioPersistenceService(
        PaperPortfolioRepository(value.data_root / "p8_portfolios.json")
    )
    new_entry_executor = NewEntryPaperLifecycleExecutor(
        portfolio_persistence_service=portfolio_persistence,
        trade_persistence_service=trade_persistence,
    )
    authorities = CompleteCycleAuthoritySetV1(
        data_authority=data_authority,
        session_authority=session_authority,
        analysis_authority=analysis_authority,
        opportunity_authority=opportunity_authority,
        p6_input_factory=_observe_only_p6_input_factory,
        new_entry_input_factory=_observe_only_new_entry_input_factory,
    )
    opportunity_executor = CompletePaperOrchestrationCycleExecutor(
        authorities=authorities,
        new_entry_stage_authority=new_entry_executor.execute,
        clock=clock,
    )

    monitoring_authority = ExistingPositionMonitoringExecutor(
        trade_replay_coordinator=PaperTradeReplayCoordinator(
            trade_persistence
        ),
        portfolio_lifecycle_coordinator=(
            PaperPortfolioLifecycleCoordinator(portfolio_persistence)
        ),
    )
    monitoring_executor = ExistingPositionMonitoringCycleExecutor(
        monitoring_input_factory=_no_active_position_monitoring_input,
        monitoring_authority=monitoring_authority.execute,
        clock=clock,
    )
    paths = build_certified_persistence_paths(value.data_root)
    coordinators = build_certified_coordinators(
        opportunity_cycle_executor=opportunity_executor,
        monitoring_cycle_executor=monitoring_executor,
        clock=clock,
        paths=paths,
    )
    dashboard = build_certified_dashboard_publication(clock=clock)
    controls = CertifiedOperatorControls(
        observe_only=True,
        emergency_halt=value.emergency_halt,
    )
    cycle_source = CertifiedCycleSource(
        readers=readers,
        settings=value,
        clock=clock,
    )
    runtime = ContinuousPaperOrchestrationRuntimeAdapter(
        opportunity_coordinator=coordinators.opportunity_coordinator,
        opportunity_input_factory=ControlledOpportunityInputFactory(
            delegate=lambda: cycle_source("OPPORTUNITY"),
            controls=controls,
        ),
        monitoring_coordinator=coordinators.monitoring_coordinator,
        monitoring_input_factory=lambda: cycle_source("MONITORING"),
        config=ContinuousPaperOrchestrationRuntimeConfigV1(
            interval_seconds=float(value.interval_seconds),
        ),
        startup_operation=_recovery_success_empty,
        dashboard_publication_producer=dashboard.producer,
        dashboard_publication_store=dashboard.store,
    )
    return CertifiedLauncherCompositionV1(
        runtime_adapter=runtime,
        controls=controls,
        logger=CertifiedJsonLineLogger(file_path=value.log_path),
    )

