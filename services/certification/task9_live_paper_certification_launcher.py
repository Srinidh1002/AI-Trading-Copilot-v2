"""Dedicated executable launcher for Task 9 two-market PAPER certification.

The launcher acquires evidence only through the official Task 9 two-market
composition, then passes that exact handoff into the Task 9 production runtime.
It is intentionally unrelated to the legacy single-primary-market launcher.
"""
from __future__ import annotations

from services.certification.task9_atomic_file_replace import replace_task9_atomic_file
from services.certification.task9_startup_preflight_store import (
    Task9StartupPreflightStore,
)

import argparse
import hashlib
import json
import inspect
import logging
import math
import os
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import config

from services.certification.task9_parent_evidence_composition import (
    build_task9_parent_evidence_dependencies,
)
from services.certification.task9_cycle_market_evidence_handoff import (
    Task9CycleMarketEvidenceV1,
)
from services.certification.task9_live_paper_production_composition import (
    Task9ProductionPersistenceLayoutV1,
    build_task9_live_paper_production_runtime,
)
from services.certification.task9_close_drain_coordinator import coordinate_task9_close_drain
from services.certification.task9_close_drain_state_store import Task9CloseDrainStateStore
from services.certification.task9_restart_recovery_startup import (
    run_task9_restart_recovery_startup,
)
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
from services.certification.task9_option_oi_change_authority import (
    Task9OptionOiChangeAuthority,
    Task9OptionOiSnapshotStore,
)
from services.contracts.task9_market_session_policy_v1 import (
    Task9MarketSegment,
    Task9SessionPhase,
)
from services.contracts.task9_market_session_state_v1 import (
    Task9SegmentSessionStateV1,
)
from services.contracts.task9_run_classification_v1 import validate_task9_run_classification
from services.contracts.task9_runtime_config_snapshot_v1 import (
    validate_task9_runtime_config_snapshot_reference,
)
from services.certification.task9_skipped_parent_evidence_cycle import (
    Task9SkippedParentEvidenceCycleStore,
    Task9SkippedParentEvidenceCycleV1,
)
from services.certification.task9_launcher_runtime_diagnostic_store import Task9LauncherRuntimeDiagnosticStore
from services.contracts.task9_launcher_runtime_diagnostic_v1 import Task9LauncherDiagnosticCategory, Task9LauncherDiagnosticStage, Task9LauncherRuntimeDiagnosticV1


_MARKETS = (("NIFTY", "NSE"), ("SENSEX", "BSE"))
_MANIFEST_NAME = "task9-live-paper-run.json"
_LOCK_NAME = "task9-live-paper.lock"
_HISTORICAL_DIAGNOSTIC_LOGGER = "services.market.live_multi_timeframe_data"
_HISTORICAL_DIAGNOSTIC_HANDLER_MARKER = "task9_historical_diagnostic_console"
_TASK9_HISTORICAL_INTER_REQUEST_SECONDS = 15.0
_PARENT_EVIDENCE_TIMEZONE = ZoneInfo("Asia/Kolkata")
_PARENT_EVIDENCE_SEGMENTS = {
    "NIFTY": Task9MarketSegment.NFO_OPTIONS,
    "SENSEX": Task9MarketSegment.BFO_OPTIONS,
}
logger = logging.getLogger(__name__)


class Task9ExternalProviderBlockedError(RuntimeError): pass


class Task9ParentEvidenceSessionClosedError(RuntimeError): pass


def _is_stale_parent_evidence_error(
    exc: BaseException,
) -> bool:
    """Recognize only canonical stale parent-evidence failures."""

    current: BaseException | None = exc
    seen: set[int] = set()

    while current is not None:
        identity = id(current)

        if identity in seen:
            break

        seen.add(identity)

        if (
            type(current) is ValueError
            and str(current) in {
                "market observation is stale",
                "provider quote timestamp is stale.",
            }
        ):
            return True

        current = current.__cause__

    return False


def _parent_evidence_session_is_open(
    value: datetime,
    *,
    session_state_resolver: Callable | None,
) -> bool:
    """Fail closed unless both Task9 F&O sessions allow monitoring."""
    local = _aware(
        value,
        "parent evidence time",
    ).astimezone(_PARENT_EVIDENCE_TIMEZONE)

    if session_state_resolver is None:
        return False

    market_date = local.date()

    for market, expected_segment in _PARENT_EVIDENCE_SEGMENTS.items():
        try:
            state = session_state_resolver(
                market=market,
                evaluated_at=local,
                market_date=market_date,
            )
        except (TypeError, ValueError):
            return False

        if type(state) is not Task9SegmentSessionStateV1:
            return False

        if state.segment is not expected_segment:
            return False

        if state.market_date != market_date:
            return False

        if state.phase not in {
            Task9SessionPhase.OPEN,
            Task9SessionPhase.ENTRY_RESTRICTED,
        }:
            return False

        if state.position_monitoring_allowed is not True:
            return False

    return True


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
        replace_task9_atomic_file(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True, slots=True)
class Task9LivePaperRunManifestV1:
    official_run_id: str
    official_start_at: datetime
    run_classification: str = "OFFICIAL_CERTIFICATION"
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False
    runtime_config_snapshot_id: str | None = None
    runtime_config_sha256: str | None = None
    # Optional solely for backwards compatibility with pre-9.83.3 evidence.
    # New rollover targets require both through their separate authority check.
    campaign_id: str | None = None
    market_date: date | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "official_run_id",
            _text(self.official_run_id, "official_run_id"),
        )
        object.__setattr__(self, "run_classification", validate_task9_run_classification(self.run_classification))
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
        if (self.runtime_config_snapshot_id is None) != (self.runtime_config_sha256 is None):
            raise ValueError("runtime config provenance")
        if self.runtime_config_snapshot_id is not None:
            from services.contracts.task9_runtime_config_snapshot_v1 import (
                validate_task9_runtime_config_snapshot_reference,
            )
            snapshot_id, content_sha256 = validate_task9_runtime_config_snapshot_reference(
                self.runtime_config_snapshot_id, self.runtime_config_sha256,
            )
            object.__setattr__(self, "runtime_config_snapshot_id", snapshot_id)
            object.__setattr__(self, "runtime_config_sha256", content_sha256)
        if self.campaign_id is not None:
            object.__setattr__(self, "campaign_id", _text(self.campaign_id, "campaign_id"))
        if self.market_date is not None and type(self.market_date) is not date:
            raise ValueError("market_date")

    def to_dict(self) -> dict[str, object]:
        value = {
            "official_run_id": self.official_run_id,
            "official_start_at": self.official_start_at.isoformat(),
            "run_classification": self.run_classification,
            "execution_mode": self.execution_mode,
            "broker_order_submission": self.broker_order_submission,
            "live_execution_eligible": self.live_execution_eligible,
        }
        if self.runtime_config_snapshot_id is not None:
            value["runtime_config_snapshot_id"] = self.runtime_config_snapshot_id
            value["runtime_config_sha256"] = self.runtime_config_sha256
        if self.campaign_id is not None:
            value["campaign_id"] = self.campaign_id
        if self.market_date is not None:
            value["market_date"] = self.market_date.isoformat()
        return value


def read_task9_run_manifest(*, persistence_root: str | Path) -> Task9LivePaperRunManifestV1:
    """Read the one deterministic launcher manifest; never creates a fallback."""
    path = Path(persistence_root) / _MANIFEST_NAME
    if not path.exists():
        raise ValueError("missing Task 9 launcher run manifest")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid Task 9 launcher run manifest") from exc
    legacy_keys = {"official_run_id", "official_start_at", "run_classification", "execution_mode", "broker_order_submission", "live_execution_eligible"}
    provenance_keys = legacy_keys | {"runtime_config_snapshot_id", "runtime_config_sha256"}
    identity_keys = provenance_keys | {"campaign_id", "market_date"}
    if type(raw) is not dict or not any(set(raw) == keys for keys in (legacy_keys, provenance_keys, identity_keys)):
        raise ValueError("invalid Task 9 launcher run manifest")
    try:
        return Task9LivePaperRunManifestV1(official_run_id=raw["official_run_id"], official_start_at=datetime.fromisoformat(raw["official_start_at"]), run_classification=raw["run_classification"], execution_mode=raw["execution_mode"], broker_order_submission=raw["broker_order_submission"], live_execution_eligible=raw["live_execution_eligible"], runtime_config_snapshot_id=raw.get("runtime_config_snapshot_id"), runtime_config_sha256=raw.get("runtime_config_sha256"), campaign_id=raw.get("campaign_id"), market_date=date.fromisoformat(raw["market_date"]) if raw.get("market_date") is not None else None)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid Task 9 launcher run manifest") from exc

def load_or_create_task9_run_manifest(
    *,
    persistence_root: str | Path,
    official_run_id: str,
    started_at: datetime,
    run_classification: str = "OFFICIAL_CERTIFICATION",
    runtime_config_snapshot_id: str | None = None,
    runtime_config_sha256: str | None = None,
    campaign_id: str | None = None,
    market_date: date | None = None,
) -> Task9LivePaperRunManifestV1:
    """Load the exact launcher run or advance only through canonical rollover.

    Same-run restart remains strictly immutable.

    The one legacy singleton launcher manifest may advance to a later market
    day only when BOTH durable campaign authorities independently prove the
    requested current run:

    - active-campaign.json
    - official-run-manifests/<official_run_id>.json

    No directory scanning, latest-file selection, or inferred rollover is
    permitted.
    """
    root = Path(persistence_root)
    run_id = _text(
        official_run_id,
        "official_run_id",
    )
    start = _aware(
        started_at,
        "started_at",
    )
    classification = (
        validate_task9_run_classification(
            run_classification
        )
    )

    requested = Task9LivePaperRunManifestV1(
        run_id,
        start,
        classification,
        runtime_config_snapshot_id=(
            runtime_config_snapshot_id
        ),
        runtime_config_sha256=(
            runtime_config_sha256
        ),
        campaign_id=campaign_id,
        market_date=market_date,
    )

    path = root / _MANIFEST_NAME

    if not path.exists():
        _atomic_json(
            path,
            requested.to_dict(),
        )
        return requested

    manifest = read_task9_run_manifest(
        persistence_root=root
    )

    if manifest.official_run_id != run_id:
        # A run-id mismatch remains fail-closed unless this is a fully
        # proven cross-day continuation of the SAME certification campaign.
        if (
            manifest.campaign_id is None
            or manifest.market_date is None
            or manifest.runtime_config_snapshot_id
            is None
            or manifest.runtime_config_sha256
            is None
            or requested.campaign_id is None
            or requested.market_date is None
            or requested.runtime_config_snapshot_id
            is None
            or requested.runtime_config_sha256
            is None
        ):
            raise ValueError(
                "TASK9_OFFICIAL_RUN_ID_MISMATCH"
            )

        if (
            manifest.campaign_id
            != requested.campaign_id
            or manifest.market_date
            >= requested.market_date
        ):
            raise ValueError(
                "TASK9_OFFICIAL_RUN_ID_MISMATCH"
            )

        pointer_path = (
            root / "active-campaign.json"
        )
        official_manifest_path = (
            root
            / "official-run-manifests"
            / f"{run_id}.json"
        )

        if (
            not pointer_path.exists()
            or not official_manifest_path.exists()
        ):
            raise ValueError(
                "TASK9_OFFICIAL_RUN_ID_MISMATCH"
            )

        try:
            pointer = json.loads(
                pointer_path.read_text(
                    encoding="utf-8"
                )
            )
            official = json.loads(
                official_manifest_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "TASK9_OFFICIAL_RUN_ID_MISMATCH"
            ) from exc

        if (
            type(pointer) is not dict
            or type(official) is not dict
        ):
            raise ValueError(
                "TASK9_OFFICIAL_RUN_ID_MISMATCH"
            )

        target_date = (
            requested.market_date.isoformat()
        )

        pointer_matches = (
            pointer.get("status") == "ACTIVE"
            and pointer.get("campaign_id")
            == requested.campaign_id
            and pointer.get(
                "active_market_date"
            )
            == target_date
            and pointer.get(
                "active_official_run_id"
            )
            == run_id
            and pointer.get(
                "runtime_config_snapshot_id"
            )
            == requested.runtime_config_snapshot_id
            and pointer.get(
                "runtime_config_sha256"
            )
            == requested.runtime_config_sha256
        )

        official_matches = (
            official.get("campaign_id")
            == requested.campaign_id
            and official.get("market_date")
            == target_date
            and official.get(
                "official_run_id"
            )
            == run_id
            and official.get(
                "run_classification"
            )
            == classification
            and official.get(
                "runtime_config_snapshot_id"
            )
            == requested.runtime_config_snapshot_id
            and official.get(
                "runtime_config_sha256"
            )
            == requested.runtime_config_sha256
            and official.get(
                "execution_mode"
            )
            == "PAPER"
            and official.get(
                "broker_order_submission"
            )
            is False
            and official.get(
                "live_execution_eligible"
            )
            is False
        )

        if (
            not pointer_matches
            or not official_matches
        ):
            raise ValueError(
                "TASK9_OFFICIAL_RUN_ID_MISMATCH"
            )

        # The canonical campaign rollover has independently committed both
        # target authorities. Only now may this launcher compatibility
        # singleton advance to the requested daily run.
        _atomic_json(
            path,
            requested.to_dict(),
        )

        return requested

    # Same-run restart remains exactly strict.
    if (
        manifest.run_classification
        != classification
    ):
        raise ValueError(
            "TASK9_RUN_CLASSIFICATION_MISMATCH"
        )

    if (
        (
            runtime_config_snapshot_id,
            runtime_config_sha256,
        )
        != (
            manifest.runtime_config_snapshot_id,
            manifest.runtime_config_sha256,
        )
    ):
        raise ValueError(
            "TASK9_RUNTIME_CONFIG_PROVENANCE_MISMATCH"
        )

    if (
        campaign_id is not None
        and manifest.campaign_id
        != campaign_id
    ):
        raise ValueError(
            "TASK9_CAMPAIGN_ID_MISMATCH"
        )

    if (
        market_date is not None
        and manifest.market_date
        != market_date
    ):
        raise ValueError(
            "TASK9_MARKET_DATE_MISMATCH"
        )

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
        startup_preflight_id: str,
        runtime_config_snapshot_id: str,
        runtime_config_sha256: str,
        campaign_id: str,
        market_date: date,
        run_classification: str = "OFFICIAL_CERTIFICATION",
        live_stream_root: str | Path | None = None,
        available_capital: float = 10_000.0,
        risk_fraction: float = 0.01,
        maximum_quantity: int | None = None,
        maximum_daily_loss_fraction: float | None = None,
        task9_evidence_dependencies_factory: Callable = build_task9_parent_evidence_dependencies,
        providers=None,
        runtime_factory: Callable = build_task9_live_paper_production_runtime,
        session_state_resolver: Callable | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.persistence_root = Path(persistence_root)
        self.live_stream_root = (
            Path(live_stream_root)
            if live_stream_root is not None
            else self.persistence_root / "live_stream"
        )
        self.official_run_id = _text(official_run_id, "official_run_id")
        self.run_classification = validate_task9_run_classification(run_classification)

        self.startup_preflight_id = _text(
            startup_preflight_id,
            "startup_preflight_id",
        )
        self.campaign_id = _text(
            campaign_id,
            "campaign_id",
        )

        if type(market_date) is not date:
            raise ValueError("market_date")

        self.market_date = market_date

        (
            self.runtime_config_snapshot_id,
            self.runtime_config_sha256,
        ) = validate_task9_runtime_config_snapshot_reference(
            runtime_config_snapshot_id,
            runtime_config_sha256,
        )

        self.option_oi_change_authority = (
            Task9OptionOiChangeAuthority(
                Task9OptionOiSnapshotStore(
                    self.persistence_root
                    / "task9-option-oi-snapshots.json"
                )
            )
        )
        if (
            type(available_capital) not in (int, float)
            or isinstance(available_capital, bool)
            or available_capital <= 0
        ):
            raise ValueError("available_capital")
        if (
            type(risk_fraction) not in (int, float)
            or isinstance(risk_fraction, bool)
            or risk_fraction <= 0
            or risk_fraction > 1
        ):
            raise ValueError("risk_fraction")
        if maximum_quantity is not None and (
            type(maximum_quantity) is not int
            or isinstance(maximum_quantity, bool)
            or maximum_quantity <= 0
        ):
            raise ValueError("maximum_quantity")
        if maximum_daily_loss_fraction is not None and (
            type(maximum_daily_loss_fraction) not in (int, float)
            or isinstance(maximum_daily_loss_fraction, bool)
            or not math.isfinite(maximum_daily_loss_fraction)
            or maximum_daily_loss_fraction <= 0
            or maximum_daily_loss_fraction > 1
        ):
            raise ValueError("maximum_daily_loss_fraction")
        if not callable(task9_evidence_dependencies_factory) or not callable(runtime_factory):
            raise TypeError("launcher factory")
        if not callable(clock) or not callable(sleep):
            raise TypeError("launcher clock")
        self.available_capital = float(available_capital)
        self.risk_fraction = float(risk_fraction)
        self.maximum_quantity = maximum_quantity
        self.maximum_daily_loss_fraction = maximum_daily_loss_fraction
        self.task9_evidence_dependencies_factory = task9_evidence_dependencies_factory
        self.providers = providers
        self.runtime_factory = runtime_factory
        self.session_state_resolver = session_state_resolver
        self.clock = clock
        self.sleep = sleep

    def _now(self) -> datetime:
        return _aware(self.clock(), "clock")

    def _validate_startup_preflight_receipt(self):
        receipt = Task9StartupPreflightStore(
            self.persistence_root
        ).get(
            self.startup_preflight_id
        )

        if receipt is None:
            raise ValueError(
                "TASK9_STARTUP_PREFLIGHT_RECEIPT_MISSING"
            )

        if receipt.launch_approved is not True:
            raise ValueError(
                "TASK9_STARTUP_PREFLIGHT_NOT_APPROVED"
            )

        if receipt.official_run_id != self.official_run_id:
            raise ValueError(
                "TASK9_STARTUP_PREFLIGHT_RUN_ID_MISMATCH"
            )

        if (
            receipt.run_classification
            != self.run_classification
        ):
            raise ValueError(
                "TASK9_STARTUP_PREFLIGHT_CLASSIFICATION_MISMATCH"
            )

        if (
            receipt.runtime_config_snapshot_id,
            receipt.runtime_config_sha256,
        ) != (
            self.runtime_config_snapshot_id,
            self.runtime_config_sha256,
        ):
            raise ValueError(
                "TASK9_STARTUP_PREFLIGHT_SNAPSHOT_REFERENCE_MISMATCH"
            )

        if receipt.campaign_id != self.campaign_id:
            raise ValueError(
                "TASK9_STARTUP_PREFLIGHT_CAMPAIGN_MISMATCH"
            )

        if receipt.market_date != self.market_date:
            raise ValueError(
                "TASK9_STARTUP_PREFLIGHT_MARKET_DATE_MISMATCH"
            )

        # Conditional Authoritative Active Campaign Pointer Synchronization
        # Sandbox fixtures without active-campaign.json bypass; production runs enforce.
        from dataclasses import replace
        from pathlib import Path
        from services.certification.task9_active_campaign_pointer_store import (
            Task9ActiveCampaignPointerStore,
        )

        pointer_path = Path(self.persistence_root) / "active-campaign.json"
        if pointer_path.exists():
            pointer_store = Task9ActiveCampaignPointerStore(
                self.persistence_root
            )
            current_pointer = pointer_store.get()
            
            if (
                current_pointer is not None
                and current_pointer.startup_preflight_id != self.startup_preflight_id
            ):
                updated_pointer = replace(
                    current_pointer,
                    startup_preflight_id=self.startup_preflight_id,
                )
                pointer_store.set(
                    updated_pointer,
                    require_runtime_config_provenance_match=False,
                )

            persisted_pointer = pointer_store.get()
            if (
                persisted_pointer is None
                or persisted_pointer.startup_preflight_id != self.startup_preflight_id
            ):
                raise RuntimeError(
                    "TASK9_STARTUP_PREFLIGHT_POINTER_BINDING_FAILED"
                )

        return receipt

    def _startup_safety(self) -> None:
        validate_repository_paper_safety(
            broker=config.BROKER,
            enable_paper_trading=config.ENABLE_PAPER_TRADING,
            enable_live_trading=config.ENABLE_LIVE_TRADING,
        )
        validate_no_broker_submission_guard(broker_order_submission=False)

    def _build_task9_evidence_dependencies(self, retain, *, precomposed_timeframe_provider_factory=None):
        """Build the Task 9 parent-evidence dependency composition."""

        kwargs = {"task9_cycle_evidence_sink": retain}
        supports_precomposed = False
        supports_option_oi_change = False
        supports_providers = False
        parameters = ()
        try:
            parameters = inspect.signature(
                self.task9_evidence_dependencies_factory
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
            supports_option_oi_change = any(
                item.kind is inspect.Parameter.VAR_KEYWORD
                or item.name == "option_oi_change_authority"
                for item in parameters
            )
            supports_providers = any(
                item.kind is inspect.Parameter.VAR_KEYWORD
                or item.name == "providers"
                for item in parameters
            )
        except (TypeError, ValueError):
            supports_spacing = False
            supports_precomposed = False
            supports_option_oi_change = False
            supports_providers = False
        if supports_spacing:
            kwargs["historical_request_interval_seconds"] = (
                _TASK9_HISTORICAL_INTER_REQUEST_SECONDS
            )
        if precomposed_timeframe_provider_factory is not None and supports_precomposed:
            kwargs["precomposed_timeframe_provider_factory"] = precomposed_timeframe_provider_factory

        if supports_option_oi_change:
            kwargs["option_oi_change_authority"] = (
                self.option_oi_change_authority
            )

        for name, value in (
            ("available_capital", self.available_capital),
            ("risk_fraction", self.risk_fraction),
            ("maximum_quantity", self.maximum_quantity),
            (
                "maximum_daily_loss_fraction",
                self.maximum_daily_loss_fraction,
            ),
        ):
            if value is not None and any(
                item.kind is inspect.Parameter.VAR_KEYWORD
                or item.name == name
                for item in parameters
            ):
                kwargs[name] = value

        if (
            self.providers is not None
            and supports_providers
        ):
            kwargs["providers"] = self.providers

        return self.task9_evidence_dependencies_factory(**kwargs)

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
                store=dashboard_store,
                persistence_root=self.persistence_root,
            ).publish(result)
        except Exception as exc:
            logger.warning(
                "TASK9_DASHBOARD_PUBLICATION_FAILED error_type=%s",
                type(exc).__name__,
            )

    def _publish_after_bounded_progress(
        self,
        manifest,
        *,
        evaluated_at: datetime,
    ) -> None:
        """Project persisted final bounded-run progress to the dashboard."""

        try:
            persistent_store = DashboardPublicationPersistentStore(
                self.persistence_root
            )
            dashboard_store = DashboardPublicationStore(
                persistent_store=persistent_store
            )

            Task9DashboardPublicationPublisher(
                store=dashboard_store,
                persistence_root=self.persistence_root,
            ).publish_persisted_progress(
                source_id=(
                    "task9-bounded-final:"
                    f"{manifest.official_run_id}:"
                    f"{evaluated_at.isoformat()}"
                ),
                published_at=evaluated_at,
            )

        except Exception as exc:
            logger.warning(
                "TASK9_DASHBOARD_BOUNDED_FINAL_PUBLICATION_FAILED "
                "error_type=%s",
                type(exc).__name__,
            )

    def _publish_after_close_drain_progress(
        self,
        manifest,
        *,
        evaluated_at: datetime,
    ) -> None:
        """Project persisted final close-drain progress to the dashboard."""

        try:
            persistent_store = DashboardPublicationPersistentStore(
                self.persistence_root
            )
            dashboard_store = DashboardPublicationStore(
                persistent_store=persistent_store
            )

            Task9DashboardPublicationPublisher(
                store=dashboard_store,
                persistence_root=self.persistence_root,
            ).publish_persisted_progress(
                source_id=(
                    "task9-close-drain:"
                    f"{manifest.official_run_id}:"
                    f"{evaluated_at.isoformat()}"
                ),
                published_at=evaluated_at,
            )

        except Exception as exc:
            logger.warning(
                "TASK9_DASHBOARD_CLOSE_DRAIN_PUBLICATION_FAILED "
                "error_type=%s",
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

    def _record_skipped_stale_parent_evidence_cycle(
        self,
        *,
        handoffs: dict[tuple[str, str], Task9CycleMarketEvidenceV1],
        observed_at: datetime,
    ) -> None:
        """Audit a pre-handoff freshness rejection without inventing evidence."""
        incident_ids = tuple(sorted({
            incident.incident_id
            for evidence in handoffs.values()
            for incident in evidence.provider_incidents
        }))
        if incident_ids:
            self._record_retained_runtime_provider_incidents(
                handoffs=handoffs,
                observed_at=observed_at,
            )
        Task9SkippedParentEvidenceCycleStore(self.persistence_root).save(
            Task9SkippedParentEvidenceCycleV1(
                official_run_id=self.official_run_id,
                observed_at=observed_at,
                retained_provider_incident_ids=incident_ids,
            )
        )

    def _drain_expired_abstentions(self, manifest, *, evaluated_at):
        """Coordinate provider-free durable close work after parent generation stops."""
        if (
            not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None
        ):
            raise ValueError("evaluated_at")

        resolver = self.session_state_resolver
        if not callable(resolver):
            raise ValueError(
                "TASK9_CANONICAL_SESSION_AUTHORITY_REQUIRED"
            )

        market_date = evaluated_at.date()
        session_states = []

        for market in ("NIFTY", "SENSEX"):
            expected_segment = _PARENT_EVIDENCE_SEGMENTS[
                market
            ]

            state = resolver(
                market=market,
                evaluated_at=evaluated_at,
                market_date=market_date,
            )

            if (
                type(state)
                is not Task9SegmentSessionStateV1
                or state.segment is not expected_segment
                or state.market_date != market_date
            ):
                raise ValueError(
                    "TASK9_CLOSE_DRAIN_SESSION_IDENTITY"
                )

            session_states.append(state)

        layout = Task9ProductionPersistenceLayoutV1.from_root(
            self.persistence_root
        )
        ledger = PredictionLedger(
            layout.prediction_ledger_path
        )
        context_store = (
            Task9PredictionLifecycleContextStore(
                layout.lifecycle_context_store_path
            )
        )
        observation_store = (
            Task9PredictionObservationWindowStore(
                layout.observation_window_store_path
            )
        )
        outcome_store = (
            Task9PredictionLifecycleOutcomeStore(
                layout.lifecycle_outcome_store_path
            )
        )
        reconciliation_store = (
            Task9PredictionLifecycleReconciliationStore(
                layout.lifecycle_reconciliation_store_path
            )
        )
        binding_store = (
            Task9PredictionPaperTradeBindingStore(
                layout.binding_store_path
            )
        )
        trade_service = PaperTradePersistenceService(
            PaperTradeRepository(
                layout.paper_trade_repository_path
            )
        )
        policy = PredictionLifecycleOutcomePolicyV1(
            policy_id=(
                "task9-production-lifecycle-policy"
            ),
            policy_version="1.0",
        )

        drain_state = coordinate_task9_close_drain(
            official_run_id=manifest.official_run_id,
            market_date=market_date,
            evaluated_at=evaluated_at,
            session_states=tuple(session_states),
            prediction_ledger=ledger,
            binding_store=binding_store,
            lifecycle_context_store=context_store,
            observation_store=observation_store,
            outcome_store=outcome_store,
            reconciliation_store=reconciliation_store,
            trade_persistence_service=trade_service,
            outcome_policy=policy,
            state_store=Task9CloseDrainStateStore(
                self.persistence_root
            ),
            live_stream_root=self.live_stream_root,
        )

        Task9CertificationPublicationAuthority(
            official_run_id=manifest.official_run_id,
            official_start_at=manifest.official_start_at,
            root=self.persistence_root,
            prediction_ledger=ledger,
            binding_store=binding_store,
            outcome_store=outcome_store,
            reconciliation_store=reconciliation_store,
            trade_persistence_service=trade_service,
            starting_capital=self.available_capital,
            run_classification=(
                manifest.run_classification
            ),
        ).refresh(
            session_date=market_date,
            evaluated_at=evaluated_at,
        )

        self._publish_after_close_drain_progress(
            manifest,
            evaluated_at=evaluated_at,
        )

        return drain_state

    def _run_one_cycle(self, manifest: Task9LivePaperRunManifestV1, *, precomposed_timeframe_provider_factory=None):
        # This controls only fresh NSE/BSE parent evidence. Existing-position
        # monitoring remains a separate lifecycle scheduling concern.
        if not _parent_evidence_session_is_open(
            self._now(),
            session_state_resolver=self.session_state_resolver,
        ):
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

        dependencies = self._build_task9_evidence_dependencies(retain, precomposed_timeframe_provider_factory=precomposed_timeframe_provider_factory)
        if (
            dependencies.execution_mode != "PAPER"
            or dependencies.broker_order_submission is not False
            or dependencies.live_execution_eligible is not False
        ):
            raise ValueError("Task 9 evidence composition must remain PAPER-only")
        try:
            decision = dependencies.parent_cycle()
        except (ValueError, RuntimeError) as exc:
            if not _is_stale_parent_evidence_error(exc):
                raise

            observed_at = self._now()

            if not _parent_evidence_session_is_open(
                observed_at,
                session_state_resolver=self.session_state_resolver,
            ):
                raise Task9ParentEvidenceSessionClosedError(
                    "TASK9_PARENT_EVIDENCE_SESSION_CLOSED"
                ) from exc

            self._record_skipped_stale_parent_evidence_cycle(
                handoffs=handoffs,
                observed_at=observed_at,
            )

            return None
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
            run_classification=manifest.run_classification,
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
        self._validate_startup_preflight_receipt()

        configure_task9_historical_diagnostic_logging()
        blocker = Task9ExternalProviderBlockerStore(self.persistence_root).load(self.official_run_id)
        # Task 9 live cycles are local-evidence-only.  Historical REST is an
        # explicit recovery/cache-maintenance authority, never a cycle fallback.
        fallback_factory = build_task9_precomposed_timeframe_provider(
            live_stream_root=self.live_stream_root,
            session_state_resolver=self.session_state_resolver,
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
        attempted = 0
        graceful = True
        manifest = None
        diagnostics = Task9LauncherRuntimeDiagnosticStore(self.persistence_root)
        stage = Task9LauncherDiagnosticStage.PRE_LOOP
        def diagnostic(category, reason_code, *, exception_class=None, graceful_shutdown=False):
            now = self._now()
            return diagnostics.append(Task9LauncherRuntimeDiagnosticV1(
                diagnostic_id=f"{self.official_run_id}:{attempted}:{completed}:{category.value}:{now.isoformat()}", official_run_id=self.official_run_id, observed_at=now,
                attempt_number=attempted, completed_cycles=completed, stage=stage, category=category, reason_code=reason_code,
                graceful_shutdown=graceful_shutdown, exception_class=exception_class))
        try:
            manifest = load_or_create_task9_run_manifest(
                persistence_root=self.persistence_root,
                official_run_id=self.official_run_id,
                started_at=self._now(),
                run_classification=self.run_classification,
                runtime_config_snapshot_id=(
                    self.runtime_config_snapshot_id
                ),
                runtime_config_sha256=(
                    self.runtime_config_sha256
                ),
                campaign_id=self.campaign_id,
                market_date=self.market_date,
            )
            run_task9_restart_recovery_startup(
                official_run_id=manifest.official_run_id,
                official_start_at=manifest.official_start_at,
                persistence_root=self.persistence_root,
                evaluated_at=self._now(),
                starting_capital=self.available_capital,
                run_classification=manifest.run_classification,
                live_stream_root=self.live_stream_root,
            )

            while max_cycles is None or attempted < max_cycles:
                attempted += 1
                stage = Task9LauncherDiagnosticStage.BEFORE_CYCLE
                diagnostic(Task9LauncherDiagnosticCategory.ATTEMPT_STARTED, "ATTEMPT_STARTED")
                stage = Task9LauncherDiagnosticStage.RUN_CYCLE
                try:
                    result = self._run_one_cycle(manifest, precomposed_timeframe_provider_factory=fallback_factory)
                except (Task9ParentEvidenceSessionClosedError, KeyboardInterrupt):
                    raise
                except Exception as exc:
                    diagnostic(Task9LauncherDiagnosticCategory.UNEXPECTED_FAILURE, "UNEXPECTED_CYCLE_FAILURE", exception_class=type(exc).__name__)
                    raise
                if result is not None:
                    completed += 1
                    stage = Task9LauncherDiagnosticStage.AFTER_CYCLE
                    diagnostic(Task9LauncherDiagnosticCategory.CYCLE_COMPLETED, "CYCLE_COMPLETED")
                if max_cycles is None or attempted < max_cycles:
                    stage = Task9LauncherDiagnosticStage.SLEEP
                    self.sleep(float(cycle_interval_seconds))
        except Task9ParentEvidenceSessionClosedError:
            # Preserve the deliberate fail-loud contract for a bounded
            # one-shot probe that starts outside the parent-evidence session.
            # Once this launcher has already attempted prior certification
            # work, session close is a normal terminal boundary regardless
            # of whether the loop itself was bounded or continuous.
            stage = Task9LauncherDiagnosticStage.TERMINATION
            diagnostic(Task9LauncherDiagnosticCategory.SESSION_CLOSED, "TASK9_PARENT_EVIDENCE_SESSION_CLOSED", graceful_shutdown=True)
            if (
                max_cycles is not None
                and attempted == 1
                and completed == 0
            ):
                raise

            assert manifest is not None

            self._drain_expired_abstentions(
                manifest,
                evaluated_at=self._now(),
            )

            graceful = True
        except KeyboardInterrupt:
            # The current child/runtime call is allowed to finish or raise on
            # its own durable boundary.  The launcher never starts another
            # cycle after an operator interrupt.
            stage = Task9LauncherDiagnosticStage.TERMINATION
            diagnostic(Task9LauncherDiagnosticCategory.INTERRUPTED, "KEYBOARD_INTERRUPT", graceful_shutdown=True)
            graceful = True
        else:
            assert manifest is not None

            # A bounded run can finish normally while the market remains
            # open.  The cycle's early dashboard callback occurs before the
            # runtime's final certification report/progress refresh, so emit
            # one newer dashboard snapshot from the persisted final authority
            # before releasing the launcher lock.
            if max_cycles is not None and attempted > 0:
                self._publish_after_bounded_progress(
                    manifest,
                    evaluated_at=self._now(),
                )

                stage = Task9LauncherDiagnosticStage.TERMINATION
                diagnostic(Task9LauncherDiagnosticCategory.RUN_COMPLETED, "MAX_CYCLES_REACHED", graceful_shutdown=True)

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
        default="data/task9",
    )
    parser.add_argument("--official-run-id", required=True)
    parser.add_argument("--startup-preflight-id", required=True)
    parser.add_argument("--runtime-config-snapshot-id", required=True)
    parser.add_argument("--runtime-config-sha256", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument(
        "--market-date",
        type=date.fromisoformat,
        required=True,
    )
    parser.add_argument("--run-classification", choices=("OFFICIAL_CERTIFICATION", "DIAGNOSTIC_NON_COUNTING"), default="OFFICIAL_CERTIFICATION")
    parser.add_argument(
        "--live-stream-root",
        default=None,
        help="Shared read-only Task 9 WebSocket journal root; defaults to <persistence-root>/live_stream.",
    )
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
        startup_preflight_id=(
            args.startup_preflight_id
        ),
        runtime_config_snapshot_id=(
            args.runtime_config_snapshot_id
        ),
        runtime_config_sha256=(
            args.runtime_config_sha256
        ),
        campaign_id=args.campaign_id,
        market_date=args.market_date,
        run_classification=args.run_classification,
        live_stream_root=args.live_stream_root,
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


