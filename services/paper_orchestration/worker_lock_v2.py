"""Logical-market ownership locks shared by manual and supervised workers."""

from __future__ import annotations

from pathlib import Path

from services.paper_orchestration.process_lock_v2 import ProcessLockV2, lock_available

_REPO_ROOT = Path(__file__).resolve().parents[2]
_locks: dict[str, ProcessLockV2] = {}


def market_lock_path(market: str) -> Path:
    return _REPO_ROOT / "logs" / "supervisor" / "workers" / f"{market.upper()}.lock"


def acquire_market_worker_lock(market: str) -> ProcessLockV2:
    key = market.upper()
    if key not in _locks:
        _locks[key] = ProcessLockV2(
            market_lock_path(key), role=f"WORKER:{key}"
        ).acquire()
    return _locks[key]


def market_worker_available(market: str) -> bool:
    return lock_available(market_lock_path(market), role=f"WORKER:{market.upper()}")
