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

        if self.observe_only is not True:
            raise ValueError(
                "certified composition must start observe-only"
            )

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
class CertifiedRuntimeProviderBundleV1:
    quote_reader: QuoteReader
    analysis_pipeline: object
    option_decision_pipeline: object
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
) -> CertifiedLauncherCompositionV1:
    value = (
        settings
        if settings is not None
        else CertifiedRuntimeCompositionSettingsV1()
    )

    if (
        type(value)
        is not CertifiedRuntimeCompositionSettingsV1
    ):
        raise TypeError(
            "settings must be exact "
            "CertifiedRuntimeCompositionSettingsV1"
        )

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
        interval_seconds=value.interval_seconds,
        observe_only=True,
        emergency_halt=value.emergency_halt,
    )

    if safety.observe_only is not True:
        raise ValueError(
            "observe-only safety invariant failed"
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

    readers = CertifiedLiveProviderReaders(
        quote_reader=provider_bundle.quote_reader,
        analysis_pipeline=(
            provider_bundle.analysis_pipeline
        ),
        option_decision_pipeline=(
            provider_bundle.option_decision_pipeline
        ),
        available_capital=value.available_capital,
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
    )

    authorities = CompleteCycleAuthoritySetV1(
        data_authority=data_authority,
        session_authority=session_authority,
        analysis_authority=analysis_authority,
        opportunity_authority=opportunity_authority,
        p6_input_factory=(
            _observe_only_p6_input_factory
        ),
        new_entry_input_factory=(
            _observe_only_new_entry_input_factory
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
        observe_only=True,
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
    )