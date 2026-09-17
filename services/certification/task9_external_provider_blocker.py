"""Durable Task 9 historical-provider blocker; never places orders."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path


BLOCKER_CODE = "EXTERNAL_PROVIDER_CLIENT_CODE_QUOTA_STATE"
SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1
FILE_NAME = "task9-external-provider-blocker.json"
RUNTIME_INCIDENT_LEDGER_FILE_NAME = (
    "task9-external-provider-runtime-incidents.json"
)
LOCK_NAME = "task9-external-provider-probe.lock"

PROVIDER = "ANGEL_ONE"
ENDPOINT = "historical-data"

ACTIVE = "ACTIVE"
CLEARED = "CLEARED"

DEFAULT_PROBE_LEASE_STALE_SECONDS = 7200.0

_RATE_LIMIT_DELAYS_SECONDS = (120.0, 300.0, 900.0, 3600.0)
_RATE_LIMIT_FAILURE_REASON = "HISTORICAL-DATA_RATE_LIMITED"


class Task9ExternalProviderBlockerError(RuntimeError):
    """Raised when Task 9 external-provider blocker state is unsafe."""


class Task9RuntimeProviderIncidentLedger:
    """Durable idempotency authority for sanitized runtime provider incidents."""

    SCHEMA_VERSION = 1

    def __init__(self, persistence_root):
        self.root = Path(persistence_root)
        self.path = self.root / RUNTIME_INCIDENT_LEDGER_FILE_NAME

    def load(self, official_run_id):
        if not self.path.exists():
            return {
                "schema_version": self.SCHEMA_VERSION,
                "official_run_id": official_run_id,
                "incidents": {},
            }

        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_INCIDENT_LEDGER_CORRUPT"
            ) from exc

        if (
            type(value) is not dict
            or set(value) != {"schema_version", "official_run_id", "incidents"}
            or value.get("schema_version") != self.SCHEMA_VERSION
            or value.get("official_run_id") != official_run_id
            or type(value.get("incidents")) is not dict
        ):
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_INCIDENT_LEDGER_INVALID"
            )

        for incident_id, observed_at in value["incidents"].items():
            try:
                _validate_runtime_incident_id(incident_id)
            except ValueError as exc:
                raise Task9ExternalProviderBlockerError(
                    "TASK9_EXTERNAL_PROVIDER_INCIDENT_LEDGER_INVALID"
                ) from exc
            _parse_aware_iso_datetime(
                observed_at,
                field_name="incident_observed_at",
            )

        return value

    def contains(self, official_run_id, incident_id):
        return incident_id in self.load(official_run_id)["incidents"]

    def record(self, official_run_id, *, incident_id, observed_at):
        incident_id = _validate_runtime_incident_id(incident_id)
        value = self.load(official_run_id)
        if incident_id in value["incidents"]:
            return False
        value["incidents"][incident_id] = observed_at.isoformat()
        _atomic_write_json(self.path, value)
        return True


def _require_aware_datetime(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(field_name)

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(field_name)

    return value


def _parse_aware_iso_datetime(
    value,
    *,
    field_name: str,
    allow_none: bool = False,
):
    if value is None:
        if allow_none:
            return None
        raise Task9ExternalProviderBlockerError(
            "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
        )

    if not isinstance(value, str):
        raise Task9ExternalProviderBlockerError(
            "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
        )

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise Task9ExternalProviderBlockerError(
            "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Task9ExternalProviderBlockerError(
            "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
        )

    return parsed


def _atomic_write_json(path: Path, value) -> None:
    """Write deterministic JSON through a durable, Windows-safe replace."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            json.dump(
                value,
                handle,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_runtime_incident_id(incident_id: object) -> str:
    """Accept only the sanitized deterministic Task 9 incident identity."""

    if type(incident_id) is not str or not incident_id.strip():
        raise ValueError("incident_id")

    normalized = incident_id.strip()
    prefix = "task9-provider-incident:"

    if not normalized.startswith(prefix):
        raise ValueError("incident_id")

    remainder = normalized[len(prefix):]

    try:
        observation_id, exchange, endpoint, timeframe, failure_reason = (
            remainder.rsplit(":", 4)
        )
    except ValueError as exc:
        raise ValueError("incident_id") from exc

    if (
        not observation_id
        or exchange not in {"NSE", "BSE"}
        or endpoint != "historical-data"
        or timeframe not in {"5m", "15m", "1h", "1d"}
        or failure_reason != "HISTORICAL-DATA_RATE_LIMITED"
    ):
        raise ValueError("incident_id")

    return normalized


class Task9ExternalProviderBlockerStore:
    """Persistent authority for Task 9 historical-provider recovery blocking."""

    def __init__(
        self,
        persistence_root,
        *,
        time_function=time.time,
    ):
        self.root = Path(persistence_root)
        self.path = self.root / FILE_NAME
        self.runtime_incident_ledger = Task9RuntimeProviderIncidentLedger(
            self.root
        )
        self.lock_path = self.root / LOCK_NAME

        self.time_function = time_function

    def _write(self, value):
        """Atomically persist blocker state."""
        _atomic_write_json(self.path, value)

    def load(self, official_run_id, *, migrate=True):
        """Load and strictly validate persisted blocker state."""

        if not self.path.exists():
            return None

        try:
            raw = self.path.read_text(
                encoding="utf-8"
            )
            value = json.loads(raw)

        except (OSError, json.JSONDecodeError) as exc:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_CORRUPT"
            ) from exc

        legacy_fields = {
            "schema_version",
            "blocker_code",
            "provider",
            "endpoint",
            "status",
            "first_seen_at",
            "last_seen_at",
            "last_probe_at",
            "last_probe_result",
            "last_failure_reason",
            "next_probe_not_before",
            "occurrence_count",
            "official_run_id",
        }
        required_fields = legacy_fields | {
            "consecutive_rate_limit_count",
        }

        if type(value) is not dict:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
            )

        if value.get("schema_version") == LEGACY_SCHEMA_VERSION:
            if set(value) != legacy_fields:
                raise Task9ExternalProviderBlockerError(
                    "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
                )
            self._validate(value, official_run_id, legacy=True)
            if not migrate:
                return value
            migrated = dict(value)
            migrated.update(
                schema_version=SCHEMA_VERSION,
                consecutive_rate_limit_count=(
                    1
                    if (
                        value["status"] == ACTIVE
                        and value["last_failure_reason"]
                        == _RATE_LIMIT_FAILURE_REASON
                    )
                    else 0
                ),
            )
            self._write(migrated)
            return migrated

        if set(value) != required_fields:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
            )

        if value.get("schema_version") != SCHEMA_VERSION:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
            )

        self._validate(value, official_run_id, legacy=False)
        return value

    @staticmethod
    def _validate(value, official_run_id, *, legacy):
        if value.get("blocker_code") != BLOCKER_CODE:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
            )

        if value.get("provider") != PROVIDER:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
            )

        if value.get("endpoint") != ENDPOINT:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
            )

        if value.get("official_run_id") != official_run_id:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
            )

        if value.get("status") not in {
            ACTIVE,
            CLEARED,
        }:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
            )

        occurrence_count = value.get(
            "occurrence_count"
        )

        if (
            type(occurrence_count) is not int
            or occurrence_count < 0
        ):
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
            )

        if not legacy:
            consecutive_rate_limit_count = value.get(
                "consecutive_rate_limit_count"
            )
            if (
                type(consecutive_rate_limit_count) is not int
                or consecutive_rate_limit_count < 0
            ):
                raise Task9ExternalProviderBlockerError(
                    "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
                )

        _parse_aware_iso_datetime(
            value.get("first_seen_at"),
            field_name="first_seen_at",
        )

        _parse_aware_iso_datetime(
            value.get("last_seen_at"),
            field_name="last_seen_at",
        )

        _parse_aware_iso_datetime(
            value.get("next_probe_not_before"),
            field_name="next_probe_not_before",
        )

        _parse_aware_iso_datetime(
            value.get("last_probe_at"),
            field_name="last_probe_at",
            allow_none=True,
        )

        last_probe_result = value.get(
            "last_probe_result"
        )

        if last_probe_result is not None and not isinstance(
            last_probe_result,
            str,
        ):
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
            )

        last_failure_reason = value.get(
            "last_failure_reason"
        )

        if last_failure_reason is not None and not isinstance(
            last_failure_reason,
            str,
        ):
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_INVALID"
            )

    @staticmethod
    def _rate_limit_delay_seconds(consecutive_rate_limit_count):
        if consecutive_rate_limit_count <= 0:
            return _RATE_LIMIT_DELAYS_SECONDS[3]
        if consecutive_rate_limit_count == 1:
            return _RATE_LIMIT_DELAYS_SECONDS[0]
        if consecutive_rate_limit_count == 2:
            return _RATE_LIMIT_DELAYS_SECONDS[1]
        if consecutive_rate_limit_count == 3:
            return _RATE_LIMIT_DELAYS_SECONDS[2]
        return _RATE_LIMIT_DELAYS_SECONDS[3]

    def rebase_active_rate_limit_probe_schedule(self, official_run_id):
        """Rebase an ACTIVE typed rate-limit hold to the adaptive schedule.

        This provider-free operation only shortens a legacy longer hold.  It
        deliberately preserves all blocker evidence and never clears state.
        """

        prior = self.load(official_run_id, migrate=False)
        if prior is None:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_MISSING"
            )

        if (
            prior["schema_version"] != SCHEMA_VERSION
            or prior["status"] != ACTIVE
            or prior["last_failure_reason"] != _RATE_LIMIT_FAILURE_REASON
            or prior["consecutive_rate_limit_count"] < 1
        ):
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_REBASE_NOT_ALLOWED"
            )

        last_seen_at = _parse_aware_iso_datetime(
            prior["last_seen_at"],
            field_name="last_seen_at",
        )
        current_not_before = _parse_aware_iso_datetime(
            prior["next_probe_not_before"],
            field_name="next_probe_not_before",
        )
        adaptive_not_before = last_seen_at + timedelta(
            seconds=self._rate_limit_delay_seconds(
                prior["consecutive_rate_limit_count"]
            )
        )

        if current_not_before <= adaptive_not_before:
            return prior

        value = dict(prior)
        value["next_probe_not_before"] = adaptive_not_before.isoformat()
        self._write(value)
        return value

    def record(
        self,
        official_run_id,
        *,
        observed_at,
        probe_at=None,
        probe_result="RATE_LIMITED",
        failure_reason="HISTORICAL-DATA_RATE_LIMITED",
        increment_occurrence=True,
    ):
        """Create or update the ACTIVE blocker."""

        observed_at = _require_aware_datetime(
            observed_at,
            field_name="observed_at",
        )

        if probe_at is not None:
            probe_at = _require_aware_datetime(
                probe_at,
                field_name="probe_at",
            )

        prior = self.load(
            official_run_id
        )

        if prior is None:
            first_seen_at = (
                observed_at.isoformat()
            )
            previous_count = 0
            previous_probe_at = None
            previous_consecutive_rate_limit_count = 0
        else:
            first_seen_at = prior[
                "first_seen_at"
            ]
            previous_count = prior[
                "occurrence_count"
            ]
            previous_probe_at = prior[
                "last_probe_at"
            ]
            previous_consecutive_rate_limit_count = prior[
                "consecutive_rate_limit_count"
            ]

        occurrence_count = (
            previous_count
            + (
                1
                if increment_occurrence
                else 0
            )
        )
        increments_rate_limit_escalation = (
            increment_occurrence
            and probe_result == "RATE_LIMITED"
            and failure_reason == _RATE_LIMIT_FAILURE_REASON
        )
        consecutive_rate_limit_count = (
            previous_consecutive_rate_limit_count + 1
            if increments_rate_limit_escalation
            else previous_consecutive_rate_limit_count
        )

        next_probe_not_before = (
            observed_at
            + timedelta(
                seconds=self._rate_limit_delay_seconds(
                    consecutive_rate_limit_count
                )
            )
        )

        value = {
            "schema_version": SCHEMA_VERSION,
            "blocker_code": BLOCKER_CODE,
            "provider": PROVIDER,
            "endpoint": ENDPOINT,
            "status": ACTIVE,
            "first_seen_at": first_seen_at,
            "last_seen_at": (
                observed_at.isoformat()
            ),
            "last_probe_at": (
                probe_at.isoformat()
                if probe_at is not None
                else previous_probe_at
            ),
            "last_probe_result": (
                probe_result
            ),
            "last_failure_reason": (
                failure_reason
            ),
            "next_probe_not_before": (
                next_probe_not_before.isoformat()
            ),
            "occurrence_count": (
                occurrence_count
            ),
            "consecutive_rate_limit_count": (
                consecutive_rate_limit_count
            ),
            "official_run_id": (
                official_run_id
            ),
        }

        self._write(value)

        return value

    def record_runtime_rate_limit(
        self,
        official_run_id,
        *,
        observed_at,
        incident_id,
    ):
        """Reactivate the blocker from one retained outbound rate-limit event.

        A normal runtime event is not a recovery probe: its recorded state
        deliberately leaves ``last_probe_*`` untouched.
        """

        observed_at = _require_aware_datetime(
            observed_at,
            field_name="observed_at",
        )
        incident_id = _validate_runtime_incident_id(incident_id)

        if self.runtime_incident_ledger.contains(official_run_id, incident_id):
            existing = self.load(official_run_id)
            if existing is None:
                raise Task9ExternalProviderBlockerError(
                    "TASK9_EXTERNAL_PROVIDER_INCIDENT_LEDGER_ORPHANED"
                )
            return existing

        prior = self.load(official_run_id)
        if prior is None:
            first_seen_at = observed_at.isoformat()
            occurrence_count = 1
            last_probe_at = None
            last_probe_result = None
            consecutive_rate_limit_count = 1
        else:
            first_seen_at = prior["first_seen_at"]
            occurrence_count = prior["occurrence_count"] + 1
            last_probe_at = prior["last_probe_at"]
            last_probe_result = prior["last_probe_result"]
            consecutive_rate_limit_count = (
                prior["consecutive_rate_limit_count"] + 1
            )

        value = {
            "schema_version": SCHEMA_VERSION,
            "blocker_code": BLOCKER_CODE,
            "provider": PROVIDER,
            "endpoint": ENDPOINT,
            "status": ACTIVE,
            "first_seen_at": first_seen_at,
            "last_seen_at": observed_at.isoformat(),
            "last_probe_at": last_probe_at,
            "last_probe_result": last_probe_result,
            "last_failure_reason": "HISTORICAL-DATA_RATE_LIMITED",
            "next_probe_not_before": (
                observed_at + timedelta(
                    seconds=self._rate_limit_delay_seconds(
                        consecutive_rate_limit_count
                    )
                )
            ).isoformat(),
            "occurrence_count": occurrence_count,
            "consecutive_rate_limit_count": consecutive_rate_limit_count,
            "official_run_id": official_run_id,
        }

        self._write(value)
        self.runtime_incident_ledger.record(
            official_run_id,
            incident_id=incident_id,
            observed_at=observed_at,
        )
        return value

    def clear(
        self,
        official_run_id,
        *,
        observed_at,
    ):
        """Persist successful recovery while preserving blocker history."""

        observed_at = _require_aware_datetime(
            observed_at,
            field_name="observed_at",
        )

        prior = self.load(
            official_run_id
        )

        if prior is None:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_BLOCKER_MISSING"
            )

        value = dict(prior)

        value.update(
            status=CLEARED,
            last_seen_at=(
                observed_at.isoformat()
            ),
            last_probe_at=(
                observed_at.isoformat()
            ),
            last_probe_result="SUCCESS",
            last_failure_reason=None,
            next_probe_not_before=(
                observed_at.isoformat()
            ),
            consecutive_rate_limit_count=0,
        )

        self._write(value)

        return value

    def acquire_probe_lease(
        self,
        *,
        stale_after_seconds=(
            DEFAULT_PROBE_LEASE_STALE_SECONDS
        ),
    ):
        """Acquire exclusive recovery-probe ownership."""

        try:
            stale_after_seconds = float(
                stale_after_seconds
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "stale_after_seconds"
            ) from exc

        if stale_after_seconds < 0:
            raise ValueError(
                "stale_after_seconds"
            )

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        acquired_now = float(
            self.time_function()
        )

        try:
            with self.lock_path.open(
                "x",
                encoding="utf-8",
                newline="",
            ) as handle:
                handle.write(
                    str(acquired_now)
                )
                handle.flush()
                os.fsync(
                    handle.fileno()
                )

            return

        except FileExistsError as exc:
            try:
                raw = self.lock_path.read_text(
                    encoding="utf-8"
                )
                acquired_at = float(raw)

            except (
                OSError,
                TypeError,
                ValueError,
            ) as read_exc:
                raise Task9ExternalProviderBlockerError(
                    "TASK9_EXTERNAL_PROVIDER_PROBE_LOCK_INVALID"
                ) from read_exc

            current = float(
                self.time_function()
            )

            age_seconds = (
                current - acquired_at
            )

            if age_seconds < 0:
                raise Task9ExternalProviderBlockerError(
                    "TASK9_EXTERNAL_PROVIDER_PROBE_LOCK_INVALID"
                )

            if age_seconds <= stale_after_seconds:
                raise Task9ExternalProviderBlockerError(
                    "TASK9_EXTERNAL_PROVIDER_PROBE_IN_PROGRESS"
                ) from exc

            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as unlink_exc:
                raise Task9ExternalProviderBlockerError(
                    "TASK9_EXTERNAL_PROVIDER_PROBE_LOCK_INVALID"
                ) from unlink_exc

            return self.acquire_probe_lease(
                stale_after_seconds=(
                    stale_after_seconds
                )
            )

    def release_probe_lease(self):
        """Release this recovery process' create-only probe lease."""

        try:
            self.lock_path.unlink(
                missing_ok=True
            )
        except OSError as exc:
            raise Task9ExternalProviderBlockerError(
                "TASK9_EXTERNAL_PROVIDER_PROBE_LOCK_RELEASE_FAILED"
            ) from exc
