"""Task 9 non-destructive persistence writability probe.

Each target receives a unique probe only:
exclusive create -> flush/fsync -> atomic replace -> exact readback ->
cleanup.

No production record is opened, overwritten, or deleted.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

from services.certification.task9_atomic_file_replace import (
    replace_task9_atomic_file,
)
from services.contracts.task9_persistence_writability_proof_v1 import (
    Task9PersistenceProbeStatus,
    Task9PersistenceRootProbeV1,
    Task9PersistenceWritabilityProofV1,
)


_PAYLOAD = (
    b"TASK9_PERSISTENCE_WRITABILITY_PROBE_V1\n"
)


def _aware(
    value: object,
    name: str,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)

    return value


def _probe_one_root(
    *,
    root_kind: str,
    root: Path,
) -> Task9PersistenceRootProbeV1:
    token = uuid.uuid4().hex

    temporary = (
        root
        / f".task9-writability-{token}.tmp"
    )

    destination = (
        root
        / f".task9-writability-{token}.probe"
    )

    directory_ready = False
    exclusive_create_succeeded = False
    file_fsync_succeeded = False
    atomic_replace_succeeded = False
    readback_verified = False
    cleanup_succeeded = False

    try:
        root.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not root.is_dir():
            raise OSError(
                "probe root is not directory"
            )

        directory_ready = True

        with temporary.open(
            "xb",
        ) as handle:
            exclusive_create_succeeded = True

            handle.write(
                _PAYLOAD
            )

            handle.flush()
            os.fsync(
                handle.fileno()
            )

            file_fsync_succeeded = True

        if destination.exists():
            raise OSError(
                "probe destination collision"
            )

        replace_task9_atomic_file(
            temporary,
            destination,
        )

        atomic_replace_succeeded = True

        readback_verified = (
            destination.read_bytes()
            == _PAYLOAD
        )

    except (
        OSError,
        ValueError,
    ):
        pass

    finally:
        cleanup_ok = True

        for path in (
            temporary,
            destination,
        ):
            try:
                path.unlink(
                    missing_ok=True
                )
            except OSError:
                cleanup_ok = False

        cleanup_succeeded = (
            cleanup_ok
            and not temporary.exists()
            and not destination.exists()
        )

    return Task9PersistenceRootProbeV1(
        root_kind=root_kind,
        directory_ready=directory_ready,
        exclusive_create_succeeded=(
            exclusive_create_succeeded
        ),
        file_fsync_succeeded=(
            file_fsync_succeeded
        ),
        atomic_replace_succeeded=(
            atomic_replace_succeeded
        ),
        readback_verified=(
            readback_verified
        ),
        cleanup_succeeded=(
            cleanup_succeeded
        ),
    )


def produce_task9_persistence_writability_proof(
    *,
    persistence_root,
    live_stream_root,
    observed_at: datetime,
) -> Task9PersistenceWritabilityProofV1:
    observed_at = _aware(
        observed_at,
        "observed_at",
    )

    persistence = Path(
        persistence_root
    )

    live_stream = Path(
        live_stream_root
    )

    probes = (
        _probe_one_root(
            root_kind="PERSISTENCE_ROOT",
            root=persistence,
        ),
        _probe_one_root(
            root_kind="STARTUP_PREFLIGHT_ROOT",
            root=(
                persistence
                / "startup-preflights"
            ),
        ),
        _probe_one_root(
            root_kind="LIVE_STREAM_ROOT",
            root=live_stream,
        ),
    )

    failures = tuple(
        item.root_kind
        for item in probes
        if not item.ready
    )

    ready = not failures

    return Task9PersistenceWritabilityProofV1(
        proof_id=(
            "task9-persistence-writability:"
            f"{observed_at.isoformat()}"
        ),
        observed_at=observed_at,
        status=(
            Task9PersistenceProbeStatus.READY
            if ready
            else Task9PersistenceProbeStatus.BLOCKED_RETRYABLE
        ),
        roots=probes,
        sanitized_reason=(
            None
            if ready
            else (
                "TASK9_PERSISTENCE_PROBE_BLOCKED:"
                + ",".join(failures)
            )
        ),
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


__all__ = (
    "produce_task9_persistence_writability_proof",
)
