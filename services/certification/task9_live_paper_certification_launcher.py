"""Dedicated executable launcher for Task 9 two-market PAPER certification.

The launcher acquires evidence only through the certified Task 8 two-market
composition, then passes that exact handoff into the Task 9 production runtime.
It is intentionally unrelated to the legacy single-primary-market launcher.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import inspect
import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, time as clock_time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import config

from services.certification.task8_live_paper_default_composition import (
    build_task8_dependencies,
)
from services.certification.task9_cycle_market_evidence_handoff import (
    Task9CycleMarketEvidenceV1,
)
from services.certification.task9_live_paper_production_composition import (
    Task9ProductionPersistenceLayoutV1,
    build_task9_live_paper_production_runtime,
)
from services.certification.task9_abstention_later_observation_recovery import finalize_task9_expired_abstentions
from services.certification.task9_certification_publication import Task9CertificationPublicationAuthority
from services.certification.task9_prediction_lifecycle_context_store import Task9PredictionLifecycleContextStore
from services.certification.task9_prediction_lifecycle_outcome_store import Task9PredictionLifecycleOutcomeStore
from services.certification.task9_prediction_lifecycle_reconciliation_store import Task9PredictionLifecycleReconciliationStore
from services.certification.task9_prediction_observation_window_store import Task9PredictionObservationWindowStore
from services.certification.task9_prediction_paper_trade_binding_store import Task9PredictionPaperTradeBindingStore
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.dashboard_publication.dashboard_publication_persistent_store import (
    DashboardPublicationPersistentStore,
)
from services.market.task9_historical_websocket_composition import (
    build_task9_precomposed_timeframe_provider,
)
from services.dashboard_publication.dashboard_publication_store import (
    DashboardPublicationStore,
)
from services.dashboard_publication.task9_dashboard_publication_publisher import (
    Task9DashboardPublicationPublisher,
)
from services.paper_orchestration.certified_runtime_safety import (
    validate_no_broker_submission_guard,
    validate_repository_paper_safety,
)
from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading.paper_trade_persistence_service import PaperTradePersistenceService
from services.certification.task9_external_provider_blocker import Task9ExternalProviderBlockerStore
from services.bse_holiday_calendar import get_bse_holiday_calendar
from services.nse_holiday_calendar import get_nse_holiday_calendar


_MARKETS = (("NIFTY", "NSE"), ("SENSEX", "BSE"))
_MANIFEST_NAME = "task9-live-paper-run.json"
_LOCK_NAME = "task9-live-paper.lock"
_HISTORICAL_DIAGNOSTIC_LOGGER = "services.market.live_multi_timeframe_data"
_HISTORICAL_DIAGNOSTIC_HANDLER_MARKER = "task9_historical_diagnostic_console"
_TASK9_HISTORICAL_INTER_REQUEST_SECONDS = 15.0
_PARENT_EVIDENCE_TIMEZONE = ZoneInfo("Asia/Kolkata")
_PARENT_EVIDENCE_OPEN = clock_time(9, 15)
_PARENT_EVIDENCE_CLOSE = clock_time(15, 30)
logger = logging.getLogger(__name__)


class Task9ExternalProviderBlockedError(RuntimeError): pass


class Task9ParentEvidenceSessionClosedError(RuntimeError): pass


def _parent_evidence_session_is_open(value: datetime) -> bool:
    """Return whether fresh NSE/BSE parent evidence may contact a provider."""
    local = _aware(value, "parent evidence time").astimezone(
        _PARENT_EVIDENCE_TIMEZONE
    )
    if local.weekday() >= 5:
        return False

    trading_date = local.date()
    if (
        get_nse_holiday_calendar().is_holiday(trading_date)
        or get_bse_holiday_calendar().is_holiday(trading_date)
    ):
        return False

    market_time = local.time().replace(tzinfo=None)
    return _PARENT_EVIDENCE_OPEN <= market_time < _PARENT_EVIDENCE_CLOSE


def configure_task9_historical_diagnostic_logging(*, stream=None) -> logging.Logger:
    """Expose only sanitized historical request diagnostics for Task 9 operators."""
    diagnostic_logger = logging.getLogger(_HISTORICAL_DIAGNOSTIC_LOGGER)
    diagnostic_logger.setLevel(logging.INFO)
    diagnostic_logger.propagate = False

    for handler in diagnostic_logger.handlers:
        if getattr(handler, _HISTORICAL_DIAGNOSTIC_HANDLER_MARKER, False):
            return diagnostic_logger

    handler = logging.StreamHandler(sys.stderr if stream is None else stream)
    setattr(handler, _HISTORICAL_DIAGNOSTIC_HANDLER_MARKER, True)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    diagnostic_logger.addHandler(handler)
    return diagnostic_logger


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(name)
    return value.strip()


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True, slots=True)
class Task9LivePaperRunManifestV1:
    official_run_id: str
    official_start_at: datetime
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "official_run_id",
            _text(self.official_run_id, "official_run_id"),
        )
        object.__setattr__(
            self,
            "official_start_at",
            _aware(self.official_start_at, "official_start_at"),
        )
        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError("Task 9 launcher must remain PAPER-only")

    def to_dict(self) -> dict[str, object]:
        return {
            "official_run_id": self.official_run_id,
            "official_start_at": self.official_start_at.isoformat(),
            "execution_mode": self.execution_mode,
            "broker_order_submission": self.broker_order_submission,
            "live_execution_eligible": self.live_execution_eligible,
        }


def load_or_create_task9_run_manifest(
    *,
    persistence_root: str | Path,
    official_run_id: str,
    started_at: datetime,
) -> Task9LivePaperRunManifestV1:
    root = Path(persistence_root)
    run_id = _text(official_run_id, "official_run_id")
    start = _aware(started_at, "started_at")
    path = root / _MANIFEST_NAME
    if not path.exists():
        manifest = Task9LivePaperRunManifestV1(run_id, start)
        _atomic_json(path, manifest.to_dict())
        return manifest
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid Task 9 launcher run manifest") from exc
    if type(raw) is not dict or set(raw) != {
        "official_run_id",
        "official_start_at",
        "execution_mode",
        "broker_order_submission",
        "live_execution_eligible",
    }:
        raise ValueError("invalid Task 9 launcher run manifest")
    try:
        manifest = Task9LivePaperRunManifestV1(
            official_run_id=raw["official_run_id"],
            official_start_at=datetime.fromisoformat(raw["official_start_at"]),
            execution_mode=raw["execution_mode"],
            broker_order_submission=raw["broker_order_submission"],
            live_execution_eligible=raw["live_execution_eligible"],
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid Task 9 launcher run manifest") from exc
    if manifest.official_run_id != run_id:
        raise ValueError("TASK9_OFFICIAL_RUN_ID_MISMATCH")
    return manifest


class Task9SingleProcessLock:
    """Conservative create-only lock; stale locks require operator review."""

    def __init__(self, *, persistence_root: str | Path, official_run_id: str) -> None:
        self.path = Path(persistence_root) / _LOCK_NAME
        self.official_run_id = _text(official_run_id, "official_run_id")
        self._token = hashlib.sha256(
            f"{os.getpid()}:{time.time_ns()}:{self.official_run_id}".encode("utf-8")
        ).hexdigest()
        self._held = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "official_run_id": self.official_run_id,
            "pid": os.getpid(),
            "token": self._token,
        }
        try:
            with self.path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError as exc:
            raise RuntimeError(
                "Task 9 launcher lock already exists; do not clear a stale "
                "lock without operator review"
            ) from exc
        self._held = True

    def release(self) -> None:
        if not self._held:
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Task 9 launcher lock became unreadable") from exc
        if type(raw) is not dict or raw.get("token") != self._token:
            raise RuntimeError("Task 9 launcher lock ownership changed")
        self.path.unlink()
        self._held = False


class Task9LivePaperCycleResultStore:
    """Idempotent cycle-result persistence; it never writes progress counters."""

    def __init__(self, persistence_root: str | Path) -> None:
        self.root = Path(persistence_root) / "task9-cycle-results"

    def save(self, result) -> None:
        payload = asdict(result)
        payload["started_at"] = result.started_at.isoformat()
        payload["completed_at"] = result.completed_at.isoformat()
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=lambda value: (
                value.isoformat()
                if isinstance(value, datetime)
                else str(value)
            ),
        )
        name = hashlib.sha256(result.cycle_id.encode("utf-8")).hexdigest()
        path = self.root / f"{name}.json"
        document = {"cycle_id": result.cycle_id, "payload": json.loads(encoded)}
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError("invalid persisted Task 9 cycle result") from exc
            if existing != document:
                raise ValueError("conflicting persisted Task 9 cycle result")
            return
        _atomic_json(path, document)


@dataclass(frozen=True, slots=True)
class Task9LauncherStatsV1:
    completed_cycles: int
    graceful_shutdown: bool
    official_run_id: str
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False


class Task9LivePaperCertificationLauncher:
    """One-process Task 9 two-market cycle loop with no execution authority."""

    def __init__(
        self,
        *,
        persistence_root: str | Path,
        official_run_id: str,
        available_capital: float = 10_000.0,
        task8_dependencies_factory: Callable = build_task8_dependencies,
        runtime_factory: Callable = build_task9_live_paper_production_runtime,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.persistence_root = Path(persistence_root)
        self.official_run_id = _text(official_run_id, "official_run_id")
        if (
            type(available_capital) not in (int, float)
            or isinstance(available_capital, bool)
            or available_capital <= 0
        ):
            raise ValueError("available_capital")
        if not callable(task8_dependencies_factory) or not callable(runtime_factory):
            raise TypeError("launcher factory")
        if not callable(clock) or not callable(sleep):
            raise TypeError("launcher clock")
        self.available_capital = float(available_capital)
        self.task8_dependencies_factory = task8_dependencies_factory
        self.runtime_factory = runtime_factory
        self.clock = clock
        self.sleep = sleep

    def _now(self) -> datetime:
        return _aware(self.clock(), "clock")

    def _startup_safety(self) -> None:
        validate_repository_paper_safety(
            broker=config.BROKER,
            enable_paper_trading=config.ENABLE_PAPER_TRADING,
            enable_live_trading=config.ENABLE_LIVE_TRADING,
        )
        validate_no_broker_submission_guard(broker_order_submission=False)

    def _build_task8_dependencies(self, retain, *, precomposed_timeframe_provider_factory=None):
        """Pass Task 9 pacing explicitly without breaking legacy test factories."""

        kwargs = {"task9_cycle_evidence_sink": retain}
        supports_precomposed = False
        try:
            parameters = inspect.signature(
                self.task8_dependencies_factory
            ).parameters.values()
            supports_spacing = any(
                item.kind is inspect.Parameter.VAR_KEYWORD
                or item.name == "historical_request_interval_seconds"
                for item in parameters
            )
            supports_precomposed = any(
                item.kind is inspect.Parameter.VAR_KEYWORD
                or item.name == "precomposed_timeframe_provider_factory"
                for item in parameters
            )
        except (TypeError, ValueError):
            supports_spacing = False
        if supports_spacing:
            kwargs["historical_request_interval_seconds"] = (
                _TASK9_HISTORICAL_INTER_REQUEST_SECONDS
            )
        if precomposed_timeframe_provider_factory is not None and supports_precomposed:
            kwargs["precomposed_timeframe_provider_factory"] = precomposed_timeframe_provider_factory
        return self.task8_dependencies_factory(**kwargs)

    def _publish_after_authoritative_persist(self, result) -> None:
        """Best-effort read-only dashboard publication after runner persistence."""

        try:
            persistent_store = DashboardPublicationPersistentStore(
                self.persistence_root
            )
            dashboard_store = DashboardPublicationStore(
                persistent_store=persistent_store
            )
            Task9DashboardPublicationPublisher(
                store=dashboard_store
            ).publish(result)
        except Exception as exc:
            logger.warning(
                "TASK9_DASHBOARD_PUBLICATION_FAILED error_type=%s",
                type(exc).__name__,
            )

    def _record_retained_runtime_provider_incidents(
        self,
        *,
        handoffs: dict[tuple[str, str], Task9CycleMarketEvidenceV1],
        observed_at: datetime,
    ) -> None:
        """Persist each retained outbound throttle event exactly once.

        This runs only after both exact Task 8 handoffs exist.  It deliberately
        consumes the typed incident contract rather than inferring an incident
        from a prediction status or generic data incident.
        """

        store = Task9ExternalProviderBlockerStore(self.persistence_root)
        incident_ids = {
            incident.incident_id
            for evidence in handoffs.values()
            for incident in evidence.provider_incidents
        }
        for incident_id in sorted(incident_ids):
            store.record_runtime_rate_limit(
                self.official_run_id,
                observed_at=observed_at,
                incident_id=incident_id,
            )

    def _drain_expired_abstentions(self, manifest, *, evaluated_at):
        """Use only durable Task 9 evidence after parent generation has closed."""
        layout = Task9ProductionPersistenceLayoutV1.from_root(self.persistence_root)
        ledger = PredictionLedger(layout.prediction_ledger_path)
        context_store = Task9PredictionLifecycleContextStore(layout.lifecycle_context_store_path)
        observation_store = Task9PredictionObservationWindowStore(layout.observation_window_store_path)
        outcome_store = Task9PredictionLifecycleOutcomeStore(layout.lifecycle_outcome_store_path)
        reconciliation_store = Task9PredictionLifecycleReconciliationStore(layout.lifecycle_reconciliation_store_path)
        binding_store = Task9PredictionPaperTradeBindingStore(layout.binding_store_path)
        trade_service = PaperTradePersistenceService(PaperTradeRepository(layout.paper_trade_repository_path))
        policy = PredictionLifecycleOutcomePolicyV1(policy_id="task9-production-lifecycle-policy", policy_version="1.0")
        finalized = finalize_task9_expired_abstentions(prediction_ledger=ledger, lifecycle_context_store=context_store, observation_store=observation_store, outcome_store=outcome_store, outcome_policy=policy, evaluated_at=evaluated_at)
        Task9CertificationPublicationAuthority(official_run_id=manifest.official_run_id, official_start_at=manifest.official_start_at, root=self.persistence_root, prediction_ledger=ledger, binding_store=binding_store, outcome_store=outcome_store, reconciliation_store=reconciliation_store, trade_persistence_service=trade_service, starting_capital=self.available_capital).refresh(session_date=evaluated_at.date(), evaluated_at=evaluated_at)
        return finalized

    def _run_one_cycle(self, manifest: Task9LivePaperRunManifestV1, *, precomposed_timeframe_provider_factory=None):
        # This controls only fresh NSE/BSE parent evidence. Existing-position
        # monitoring remains a separate lifecycle scheduling concern.
        if not _parent_evidence_session_is_open(self._now()):
            raise Task9ParentEvidenceSessionClosedError(
                "TASK9_PARENT_EVIDENCE_SESSION_CLOSED"
            )

        handoffs: dict[tuple[str, str], Task9CycleMarketEvidenceV1] = {}

        def retain(evidence: Task9CycleMarketEvidenceV1) -> None:
            if type(evidence) is not Task9CycleMarketEvidenceV1:
                raise TypeError("Task 9 cycle evidence")
            identity = (
                evidence.prediction.underlying_symbol,
                evidence.prediction.exchange,
            )
            if identity not in _MARKETS or identity in handoffs:
                raise ValueError("duplicate or unsupported Task 9 handoff")
            handoffs[identity] = evidence

        dependencies = self._build_task8_dependencies(retain, precomposed_timeframe_provider_factory=precomposed_timeframe_provider_factory)
        if (
            dependencies.execution_mode != "PAPER"
            or dependencies.broker_order_submission is not False
            or dependencies.live_execution_eligible is not False
        ):
            raise ValueError("Task 8 evidence composition must remain PAPER-only")
        try:
            decision = dependencies.parent_cycle()
        except ValueError as exc:
            if (
                str(exc) == "market observation is stale"
                and not _parent_evidence_session_is_open(self._now())
            ):
                raise Task9ParentEvidenceSessionClosedError(
                    "TASK9_PARENT_EVIDENCE_SESSION_CLOSED"
                ) from exc
            raise
        if decision.selected_market is not None:
            dependencies.selected_planner(decision.selected_market)
        if set(handoffs) != set(_MARKETS):
            raise RuntimeError("Task 9 cycle requires exact NIFTY and SENSEX handoffs")
        boundary = decision.completed_at
        self._record_retained_runtime_provider_incidents(
            handoffs=handoffs,
            observed_at=boundary,
        )
        cycle_id = f"task9:{manifest.official_run_id}:{decision.parent_cycle_id}"
        result_store = Task9LivePaperCycleResultStore(self.persistence_root)
        runtime = self.runtime_factory(
            official_run_id=manifest.official_run_id,
            official_start_at=manifest.official_start_at,
            evaluated_at=boundary,
            persistence_root=self.persistence_root,
            cycle_evidence_by_market=handoffs,
            available_capital=self.available_capital,
            portfolio_id="task9-live-paper-portfolio",
            outcome_policy=PredictionLifecycleOutcomePolicyV1(
                policy_id="task9-production-lifecycle-policy",
                policy_version="1.0",
            ),
            persist=result_store.save,
            publish=self._publish_after_authoritative_persist,
        )
        if (
            runtime.execution_mode != "PAPER"
            or runtime.broker_order_submission is not False
            or runtime.live_execution_eligible is not False
        ):
            raise ValueError("Task 9 production runtime must remain PAPER-only")
        return runtime.run_cycle(cycle_id=cycle_id, evaluated_at=boundary)

    def run(
        self,
        *,
        max_cycles: int | None = None,
        cycle_interval_seconds: float = 60.0,
    ) -> Task9LauncherStatsV1:
        if max_cycles is not None and (
            type(max_cycles) is not int or max_cycles <= 0
        ):
            raise ValueError("max_cycles")
        if (
            type(cycle_interval_seconds) not in (int, float)
            or isinstance(cycle_interval_seconds, bool)
            or cycle_interval_seconds < 0
        ):
            raise ValueError("cycle_interval_seconds")
        configure_task9_historical_diagnostic_logging()
        blocker = Task9ExternalProviderBlockerStore(self.persistence_root).load(self.official_run_id)
        # Task 9 live cycles are local-evidence-only.  Historical REST is an
        # explicit recovery/cache-maintenance authority, never a cycle fallback.
        fallback_factory = build_task9_precomposed_timeframe_provider(
            live_stream_root=self.persistence_root / "live_stream"
        )
        if blocker and blocker["status"] == "ACTIVE":
            if (blocker["provider"], blocker["endpoint"], blocker["last_failure_reason"]) == ("ANGEL_ONE", "historical-data", "HISTORICAL-DATA_RATE_LIMITED"):
                pass
            else:
                now = self._now()
                not_before = datetime.fromisoformat(blocker["next_probe_not_before"])
                code = "TASK9_EXTERNAL_PROVIDER_BLOCKER_ACTIVE" if now < not_before else "RECOVERY_PROBE_REQUIRED"
                raise Task9ExternalProviderBlockedError(f"{code} blocker_code={blocker['blocker_code']} provider={blocker['provider']} endpoint={blocker['endpoint']} next_probe_not_before={blocker['next_probe_not_before']}")
        self._startup_safety()
        lock = Task9SingleProcessLock(
            persistence_root=self.persistence_root,
            official_run_id=self.official_run_id,
        )
        lock.acquire()
        completed = 0
        graceful = True
        manifest = None
        try:
            manifest = load_or_create_task9_run_manifest(
                persistence_root=self.persistence_root,
                official_run_id=self.official_run_id,
                started_at=self._now(),
            )
            while max_cycles is None or completed < max_cycles:
                self._run_one_cycle(manifest, precomposed_timeframe_provider_factory=fallback_factory)
                completed += 1
                if max_cycles is None or completed < max_cycles:
                    self.sleep(float(cycle_interval_seconds))
        except Task9ParentEvidenceSessionClosedError:
            if max_cycles is not None:
                raise
            assert manifest is not None
            self._drain_expired_abstentions(manifest, evaluated_at=self._now())
            graceful = True
        except KeyboardInterrupt:
            # The current child/runtime call is allowed to finish or raise on
            # its own durable boundary.  The launcher never starts another
            # cycle after an operator interrupt.
            graceful = True
        else:
            graceful = True
        finally:
            lock.release()
        return Task9LauncherStatsV1(
            completed_cycles=completed,
            graceful_shutdown=graceful,
            official_run_id=self.official_run_id,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Task 9 two-market live PAPER certification launcher",
    )
    parser.add_argument(
        "--persistence-root",
        default="data/paper_trading/certified_runtime/task9",
    )
    parser.add_argument("--official-run-id", required=True)
    parser.add_argument("--max-cycles", type=int, default=None)
    parser.add_argument("--cycle-interval-seconds", type=float, default=60.0)
    parser.add_argument(
        "--automated-paper",
        action="store_true",
        help="Required acknowledgement that this is automated PAPER only.",
    )
    args = parser.parse_args(argv)
    if args.automated_paper is not True:
        parser.error("--automated-paper is required; no live mode exists")
    launcher = Task9LivePaperCertificationLauncher(
        persistence_root=args.persistence_root,
        official_run_id=args.official_run_id,
    )
    stats = launcher.run(
        max_cycles=args.max_cycles,
        cycle_interval_seconds=args.cycle_interval_seconds,
    )
    print(
        "TASK9_LAUNCHER_STATS "
        f"completed_cycles={stats.completed_cycles} "
        f"graceful_shutdown={stats.graceful_shutdown}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
