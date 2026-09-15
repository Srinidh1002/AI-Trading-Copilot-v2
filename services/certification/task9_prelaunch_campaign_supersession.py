"""Fail-closed Task 9 pre-launch campaign supersession authority.

This authority exists for one narrow recovery case:

* an immutable first campaign was created;
* startup never received launch approval;
* no official runtime/cycle/trade contribution exists;
* the runtime configuration had to be repaired before certification began; and
* the repaired configuration therefore has a different content-addressed
  runtime-config snapshot.

Normal same-campaign/day/run transitions remain owned by task9_campaign_rollover.
The generic active-campaign pointer store intentionally continues to reject
cross-campaign mutation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from services.certification.task9_active_campaign_pointer_store import (
    Task9ActiveCampaignPointerStore,
)
from services.certification.task9_atomic_file_replace import (
    replace_task9_atomic_file,
)
from services.certification.task9_campaign_authority import (
    validate_task9_campaign_pointer_compatibility,
)
from services.certification.task9_campaign_index_store import (
    Task9CampaignIndexStore,
)
from services.certification.task9_campaign_manifest_store import (
    Task9CampaignManifestStore,
)
from services.certification.task9_first_campaign_initializer import (
    initialize_task9_first_campaign,
)
from services.contracts.task9_campaign_manifest_v1 import (
    Task9ActiveCampaignPointerV1,
    Task9CampaignManifestV1,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    Task9RuntimeConfigSnapshotV1,
)
from services.contracts.task9_runtime_config_v1 import (
    Task9RuntimeConfigV1,
)


_RECEIPT_SCHEMA = "task9_prelaunch_campaign_supersession_receipt.v1"


def _require_safe_runtime(
    runtime_config: Task9RuntimeConfigV1,
) -> None:
    if (
        runtime_config.execution_mode != "PAPER"
        or runtime_config.broker_order_submission is not False
        or runtime_config.live_execution_eligible is not False
        or runtime_config.run_classification
        != "OFFICIAL_CERTIFICATION"
    ):
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_REQUIRES_SAFE_OFFICIAL_PAPER"
        )


def _policy_references(
    runtime_config: Task9RuntimeConfigV1,
) -> Mapping[str, str]:
    value = getattr(
        runtime_config,
        "canonical_policy_references",
        None,
    )

    if value is None:
        value = getattr(
            runtime_config,
            "policy_references",
            None,
        )

    if not isinstance(value, Mapping):
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_POLICY_REFERENCES_MISSING"
        )

    return dict(value)


def _receipt_id(
    *,
    old_pointer: Task9ActiveCampaignPointerV1,
    runtime_config: Task9RuntimeConfigV1,
    snapshot: Task9RuntimeConfigSnapshotV1,
) -> str:
    basis = "|".join(
        (
            old_pointer.campaign_id,
            old_pointer.active_market_date.isoformat(),
            old_pointer.active_official_run_id,
            old_pointer.runtime_config_snapshot_id,
            old_pointer.runtime_config_sha256,
            runtime_config.campaign_id,
            runtime_config.market_date.isoformat(),
            runtime_config.official_run_id,
            snapshot.snapshot_id,
            snapshot.content_sha256,
        )
    )

    digest = hashlib.sha256(
        basis.encode("utf-8")
    ).hexdigest()

    return f"task9-prelaunch-supersession-{digest}"


def _receipt_path(
    root: Path,
    receipt_id: str,
) -> Path:
    return (
        root
        / "campaign-supersessions"
        / f"{receipt_id}.json"
    )


def _write_json_atomic(
    path: Path,
    document: Mapping[str, object],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        f"{path.name}.tmp"
    )

    try:
        temporary.write_text(
            json.dumps(
                dict(document),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            encoding="utf-8",
        )

        replace_task9_atomic_file(
            temporary,
            path,
        )
    finally:
        temporary.unlink(
            missing_ok=True,
        )


def _load_receipt(
    path: Path,
) -> dict[str, object] | None:
    if not path.exists():
        return None

    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_RECEIPT_CORRUPT"
        ) from exc

    if not isinstance(value, dict):
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_RECEIPT_CORRUPT"
        )

    if (
        value.get("schema_version")
        != _RECEIPT_SCHEMA
    ):
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_RECEIPT_CORRUPT"
        )

    return value


def _expected_receipt(
    *,
    receipt_id: str,
    old_pointer: Task9ActiveCampaignPointerV1,
    runtime_config: Task9RuntimeConfigV1,
    snapshot: Task9RuntimeConfigSnapshotV1,
    observed_at: datetime,
    status: str,
) -> dict[str, object]:
    return {
        "schema_version": _RECEIPT_SCHEMA,
        "receipt_id": receipt_id,
        "status": status,
        "old_campaign_id": old_pointer.campaign_id,
        "old_market_date": (
            old_pointer.active_market_date.isoformat()
        ),
        "old_official_run_id": (
            old_pointer.active_official_run_id
        ),
        "old_runtime_config_snapshot_id": (
            old_pointer.runtime_config_snapshot_id
        ),
        "old_runtime_config_sha256": (
            old_pointer.runtime_config_sha256
        ),
        "new_campaign_id": (
            runtime_config.campaign_id
        ),
        "new_market_date": (
            runtime_config.market_date.isoformat()
        ),
        "new_official_run_id": (
            runtime_config.official_run_id
        ),
        "new_runtime_config_snapshot_id": (
            snapshot.snapshot_id
        ),
        "new_runtime_config_sha256": (
            snapshot.content_sha256
        ),
        "execution_mode": "PAPER",
        "broker_order_submission": False,
        "live_execution_eligible": False,
        "prepared_at": (
            observed_at.isoformat()
        ),
    }


def _validate_existing_receipt_identity(
    existing: Mapping[str, object],
    expected: Mapping[str, object],
) -> None:
    fields = (
        "receipt_id",
        "old_campaign_id",
        "old_market_date",
        "old_official_run_id",
        "old_runtime_config_snapshot_id",
        "old_runtime_config_sha256",
        "new_campaign_id",
        "new_market_date",
        "new_official_run_id",
        "new_runtime_config_snapshot_id",
        "new_runtime_config_sha256",
        "execution_mode",
        "broker_order_submission",
        "live_execution_eligible",
    )

    if any(
        existing.get(field)
        != expected.get(field)
        for field in fields
    ):
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_RECEIPT_CONFLICT"
        )


def _require_zero_campaign_index(
    *,
    root: Path,
    campaign_id: str,
) -> None:
    index = Task9CampaignIndexStore(
        root
    ).get(
        campaign_id
    )

    if index is None:
        return

    if (
        getattr(
            index,
            "nifty_countable_total",
            None,
        )
        != 0
        or getattr(
            index,
            "sensex_countable_total",
            None,
        )
        != 0
        or tuple(
            getattr(
                index,
                "market_day_entries",
                (),
            )
        )
        != ()
    ):
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_NONZERO_CAMPAIGN"
        )


def _require_no_approved_preflight(
    *,
    root: Path,
    old_run_id: str,
    old_pointer: Task9ActiveCampaignPointerV1,
) -> None:
    if (
        old_pointer.startup_preflight_id
        is not None
    ):
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_APPROVED_PREFLIGHT_EXISTS"
        )

    preflight_root = (
        root / "startup-preflights"
    )

    if not preflight_root.exists():
        return

    for path in sorted(
        preflight_root.glob("*.json")
    ):
        try:
            raw = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "TASK9_PRELAUNCH_SUPERSESSION_PREFLIGHT_CORRUPT"
            ) from exc

        if not isinstance(raw, dict):
            raise ValueError(
                "TASK9_PRELAUNCH_SUPERSESSION_PREFLIGHT_CORRUPT"
            )

        text = json.dumps(
            raw,
            sort_keys=True,
        )

        if old_run_id not in text:
            continue

        if raw.get(
            "launch_approved"
        ) is True:
            raise ValueError(
                "TASK9_PRELAUNCH_SUPERSESSION_APPROVED_PREFLIGHT_EXISTS"
            )


def _require_no_old_run_activity(
    *,
    root: Path,
    old_pointer: Task9ActiveCampaignPointerV1,
) -> None:
    """Reject any durable old-run evidence beyond known pre-launch authority."""

    old_run_id = (
        old_pointer.active_official_run_id
    )

    allowed_exact = {
        "active-campaign.json",
        "task9-dashboard-active-campaign.json",
        (
            "campaigns/"
            f"{old_pointer.campaign_id}.json"
        ),
    }

    allowed_prefixes = (
        "runtime-config-snapshots/",
        "startup-preflights/",
        "campaign-supersessions/",
    )

    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file()
    ):
        relative = (
            path.relative_to(root)
            .as_posix()
        )

        if (
            relative in allowed_exact
            or relative.startswith(
                allowed_prefixes
            )
        ):
            continue

        try:
            content = path.read_text(
                encoding="utf-8"
            )
        except (
            OSError,
            UnicodeDecodeError,
        ):
            continue

        if old_run_id in content:
            raise ValueError(
                "TASK9_PRELAUNCH_SUPERSESSION_OLD_RUN_ACTIVITY_EXISTS"
            )


def _build_new_manifest(
    *,
    runtime_config: Task9RuntimeConfigV1,
    snapshot: Task9RuntimeConfigSnapshotV1,
) -> Task9CampaignManifestV1:
    persistence_root = Path(
        runtime_config.authoritative_persistence_root
    )

    registry_root = Path(
        runtime_config.campaign_registry_location
    ).parent

    return Task9CampaignManifestV1(
        campaign_id=runtime_config.campaign_id,
        campaign_version="1",
        campaign_status="ACTIVE",
        created_market_date=(
            runtime_config.market_date
        ),
        registry_root=(
            registry_root.as_posix()
        ),
        campaign_root=(
            (
                persistence_root
                / "campaigns"
                / runtime_config.campaign_id
            ).as_posix()
        ),
        runtime_config_snapshot_id=(
            snapshot.snapshot_id
        ),
        runtime_config_sha256=(
            snapshot.content_sha256
        ),
        canonical_policy_references=(
            _policy_references(
                runtime_config
            )
        ),
    )


def _build_new_pointer(
    *,
    runtime_config: Task9RuntimeConfigV1,
    snapshot: Task9RuntimeConfigSnapshotV1,
    observed_at: datetime,
) -> Task9ActiveCampaignPointerV1:
    persistence_root = Path(
        runtime_config.authoritative_persistence_root
    )

    registry_root = Path(
        runtime_config.campaign_registry_location
    ).parent

    campaign_root = (
        persistence_root
        / "campaigns"
        / runtime_config.campaign_id
    )

    return Task9ActiveCampaignPointerV1(
        campaign_id=runtime_config.campaign_id,
        campaign_manifest_ref=(
            persistence_root
            / "campaigns"
            / f"{runtime_config.campaign_id}.json"
        ).as_posix(),
        campaign_root=(
            campaign_root.as_posix()
        ),
        registry_root=(
            registry_root.as_posix()
        ),
        active_market_date=(
            runtime_config.market_date
        ),
        active_official_run_id=(
            runtime_config.official_run_id
        ),
        run_classification=(
            "OFFICIAL_CERTIFICATION"
        ),
        runtime_config_snapshot_id=(
            snapshot.snapshot_id
        ),
        runtime_config_sha256=(
            snapshot.content_sha256
        ),
        updated_at=observed_at,
        status="ACTIVE",
    )


def _replace_cross_campaign_pointer(
    *,
    store: Task9ActiveCampaignPointerStore,
    expected_old: Task9ActiveCampaignPointerV1,
    new_pointer: Task9ActiveCampaignPointerV1,
    new_manifest: Task9CampaignManifestV1,
) -> Task9ActiveCampaignPointerV1:
    validate_task9_campaign_pointer_compatibility(
        new_manifest,
        new_pointer,
    )

    durable_before = store.get()

    if durable_before != expected_old:
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_POINTER_CHANGED"
        )

    path = store.path
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        f"{path.name}.tmp"
    )

    try:
        temporary.write_text(
            json.dumps(
                new_pointer.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            encoding="utf-8",
        )

        replace_task9_atomic_file(
            temporary,
            path,
        )
    finally:
        temporary.unlink(
            missing_ok=True,
        )

    durable_after = store.get()

    if durable_after != new_pointer:
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_POINTER_VERIFICATION_FAILED"
        )

    validate_task9_campaign_pointer_compatibility(
        new_manifest,
        durable_after,
    )

    return durable_after


def prepare_task9_startup_campaign_authority(
    *,
    runtime_config: Task9RuntimeConfigV1,
    snapshot: Task9RuntimeConfigSnapshotV1,
    observed_at: datetime,
) -> tuple[
    Task9CampaignManifestV1,
    Task9ActiveCampaignPointerV1,
]:
    """Initialize, recover, or safely supersede pre-launch campaign authority."""

    if type(runtime_config) is not Task9RuntimeConfigV1:
        raise TypeError("runtime_config")

    if type(snapshot) is not Task9RuntimeConfigSnapshotV1:
        raise TypeError("snapshot")

    if (
        not isinstance(
            observed_at,
            datetime,
        )
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError("observed_at")

    _require_safe_runtime(
        runtime_config
    )

    root = Path(
        runtime_config.authoritative_persistence_root
    )

    pointer_store = (
        Task9ActiveCampaignPointerStore(
            root
        )
    )

    manifest_store = (
        Task9CampaignManifestStore(
            root
        )
    )

    current_pointer = (
        pointer_store.get()
    )

    if current_pointer is None:
        return initialize_task9_first_campaign(
            runtime_config=runtime_config,
            snapshot=snapshot,
            observed_at=observed_at,
        )

    # Ordinary same-campaign startup remains owned by the existing strict
    # initializer.  Snapshot/run conflicts therefore continue to fail closed.
    if (
        current_pointer.campaign_id
        == runtime_config.campaign_id
    ):
        return initialize_task9_first_campaign(
            runtime_config=runtime_config,
            snapshot=snapshot,
            observed_at=observed_at,
        )

    old_manifest = manifest_store.get(
        current_pointer.campaign_id
    )

    if old_manifest is None:
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_OLD_MANIFEST_MISSING"
        )

    validate_task9_campaign_pointer_compatibility(
        old_manifest,
        current_pointer,
    )

    if (
        old_manifest.campaign_status.value
        != "ACTIVE"
        or current_pointer.status.value
        != "ACTIVE"
    ):
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_OLD_CAMPAIGN_NOT_ACTIVE"
        )

    if (
        runtime_config.market_date
        != current_pointer.active_market_date
    ):
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_MARKET_DATE_MISMATCH"
        )

    if (
        runtime_config.official_run_id
        == current_pointer.active_official_run_id
    ):
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_NEW_RUN_REQUIRED"
        )

    old_snapshot_identity = (
        current_pointer.runtime_config_snapshot_id,
        current_pointer.runtime_config_sha256,
    )

    new_snapshot_identity = (
        snapshot.snapshot_id,
        snapshot.content_sha256,
    )

    if (
        old_snapshot_identity
        == new_snapshot_identity
    ):
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_NEW_SNAPSHOT_REQUIRED"
        )

    _require_zero_campaign_index(
        root=root,
        campaign_id=(
            current_pointer.campaign_id
        ),
    )

    _require_no_approved_preflight(
        root=root,
        old_run_id=(
            current_pointer.active_official_run_id
        ),
        old_pointer=current_pointer,
    )

    _require_no_old_run_activity(
        root=root,
        old_pointer=current_pointer,
    )

    new_manifest = _build_new_manifest(
        runtime_config=runtime_config,
        snapshot=snapshot,
    )

    new_pointer = _build_new_pointer(
        runtime_config=runtime_config,
        snapshot=snapshot,
        observed_at=observed_at,
    )

    validate_task9_campaign_pointer_compatibility(
        new_manifest,
        new_pointer,
    )

    receipt_id = _receipt_id(
        old_pointer=current_pointer,
        runtime_config=runtime_config,
        snapshot=snapshot,
    )

    receipt_path = _receipt_path(
        root,
        receipt_id,
    )

    prepared_receipt = _expected_receipt(
        receipt_id=receipt_id,
        old_pointer=current_pointer,
        runtime_config=runtime_config,
        snapshot=snapshot,
        observed_at=observed_at,
        status="PREPARED",
    )

    existing_receipt = _load_receipt(
        receipt_path
    )

    if existing_receipt is None:
        _write_json_atomic(
            receipt_path,
            prepared_receipt,
        )
    else:
        _validate_existing_receipt_identity(
            existing_receipt,
            prepared_receipt,
        )

    existing_new_manifest = (
        manifest_store.get(
            runtime_config.campaign_id
        )
    )

    if existing_new_manifest is None:
        saved_manifest = (
            manifest_store.save(
                new_manifest
            )
        )
    elif existing_new_manifest != new_manifest:
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_NEW_MANIFEST_CONFLICT"
        )
    else:
        saved_manifest = (
            existing_new_manifest
        )

    # Re-read immediately before the cross-campaign CAS-like replacement.
    durable_pointer = (
        pointer_store.get()
    )

    if durable_pointer == new_pointer:
        saved_pointer = durable_pointer
    elif durable_pointer == current_pointer:
        saved_pointer = (
            _replace_cross_campaign_pointer(
                store=pointer_store,
                expected_old=current_pointer,
                new_pointer=new_pointer,
                new_manifest=saved_manifest,
            )
        )
    else:
        raise ValueError(
            "TASK9_PRELAUNCH_SUPERSESSION_POINTER_CHANGED"
        )

    applied_receipt = dict(
        prepared_receipt
    )

    applied_receipt[
        "status"
    ] = "APPLIED"

    applied_receipt[
        "applied_at"
    ] = observed_at.isoformat()

    _write_json_atomic(
        receipt_path,
        applied_receipt,
    )

    validate_task9_campaign_pointer_compatibility(
        saved_manifest,
        saved_pointer,
    )

    return (
        saved_manifest,
        saved_pointer,
    )


__all__ = (
    "prepare_task9_startup_campaign_authority",
)
