import pytest

from services.certification.task9_runtime_config_snapshot_store import Task9RuntimeConfigSnapshotStore
from services.contracts.task9_runtime_config_snapshot_v1 import (
    Task9LegacyConfigConflictObservationV1,
    build_task9_runtime_config_snapshot,
)
from tests.test_task9_runtime_config_snapshot_v1 import _config


def test_snapshot_store_is_atomic_restart_safe_and_idempotent(tmp_path):
    snapshot = build_task9_runtime_config_snapshot(_config())
    store = Task9RuntimeConfigSnapshotStore(tmp_path)
    assert store.save(snapshot) == snapshot
    assert store.save(snapshot) == snapshot
    assert Task9RuntimeConfigSnapshotStore(tmp_path).get(snapshot.snapshot_id) == snapshot


def test_store_rejects_same_content_id_with_different_provenance_payload(tmp_path):
    snapshot = build_task9_runtime_config_snapshot(_config())
    conflict = Task9LegacyConfigConflictObservationV1(
        "capital", 25000.0, "legacy", 10000, "CURRENCY", "EXPLICIT_CANONICAL_WINS",
    )
    conflicting = build_task9_runtime_config_snapshot(_config(), conflict_observations=(conflict,))
    store = Task9RuntimeConfigSnapshotStore(tmp_path)
    store.save(snapshot)
    with pytest.raises(ValueError, match="conflicting"):
        store.save(conflicting)
