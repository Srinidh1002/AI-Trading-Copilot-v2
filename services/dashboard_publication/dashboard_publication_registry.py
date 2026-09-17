from __future__ import annotations

import threading

from .dashboard_publication_snapshot_v1 import (
    DashboardPublicationSnapshotV1,
)
from .dashboard_publication_store import DashboardPublicationStore


_lock = threading.RLock()
_store: DashboardPublicationStore | None = None


def register_dashboard_publication_store(
    store: DashboardPublicationStore,
) -> None:
    if type(store) is not DashboardPublicationStore:
        raise TypeError(
            "store must be exact DashboardPublicationStore"
        )
    global _store
    with _lock:
        _store = store


def get_registered_dashboard_publication_snapshot(
) -> DashboardPublicationSnapshotV1 | None:
    with _lock:
        store = _store
    if store is None:
        return None
    return store.get_snapshot()


def clear_dashboard_publication_store_registration() -> None:
    global _store
    with _lock:
        _store = None
