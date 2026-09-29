"""Explicit PAPER certification policy-epoch migration helpers.

This module never discovers runtime files automatically. Callers must provide
every source, ledger, authority, and archive path explicitly.

Migration contract:
- archive exact old evidence before mutation;
- refuse migration while any position/trade is active;
- refuse incoherent certification counters;
- preserve index operational history while resetting only certification
  authority for the new policy epoch;
- create a fresh MCX campaign state for a new product epoch;
- archive exact old ledgers, then atomically reset the live ledger files for the new policy epoch;
- use atomic JSON replacement for new authority/state writes.

The live PAPER runtime does not import this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ARCHIVE_SCHEMA_VERSION = "POLICY_EPOCH_ARCHIVE_V1"

EMPTY_EQUITY_DIVERSITY_STATE = {
    "trading_dates": [],
    "regimes": [],
    "session_phases": [],
    "countable_by_day": {},
}


class PolicyEpochMigrationError(RuntimeError):
    """Raised when an epoch migration cannot be performed safely."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
    except (OSError, ValueError) as exc:
        raise PolicyEpochMigrationError(f"JSON_READ_FAILED:{path.name}") from exc

    if not isinstance(value, dict):
        raise PolicyEpochMigrationError(f"JSON_NOT_OBJECT:{path.name}")

    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def _atomic_write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                payload,
                handle,
                indent=2,
                default=str,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(
            temporary,
            path,
        )

    except OSError as exc:
        try:
            os.unlink(temporary)
        except OSError:
            pass

        raise PolicyEpochMigrationError(f"ATOMIC_WRITE_FAILED:{path.name}") from exc


def _atomic_reset_file(
    path: Path,
) -> None:
    """Atomically replace one live append-only ledger with an empty file."""

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(f".{path.name}.policy_epoch_reset.tmp")

    if temporary.exists():
        raise PolicyEpochMigrationError(f"LEDGER_RESET_TEMP_EXISTS:{path.name}")

    try:
        with temporary.open(
            "xb",
        ) as handle:
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(
            temporary,
            path,
        )

    except Exception as exc:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass

        raise PolicyEpochMigrationError(f"LEDGER_RESET_FAILED:{path.name}") from exc


def _archive_exact_boundary(
    source_paths: list[Path],
    archive_dir: Path,
) -> dict[str, Any]:
    if archive_dir.exists():
        raise PolicyEpochMigrationError("ARCHIVE_DESTINATION_ALREADY_EXISTS")

    names = [path.name for path in source_paths]

    if len(names) != len(set(names)):
        raise PolicyEpochMigrationError("ARCHIVE_FILENAME_COLLISION")

    archive_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    records = []

    for source in source_paths:
        record: dict[str, Any] = {
            "source": str(source),
            "archive_name": source.name,
            "present": source.is_file(),
        }

        if source.is_file():
            destination = archive_dir / source.name

            source_hash = _sha256(source)

            shutil.copy2(
                source,
                destination,
            )

            archive_hash = _sha256(destination)

            if source_hash != archive_hash:
                raise PolicyEpochMigrationError(f"ARCHIVE_HASH_MISMATCH:{source.name}")

            record.update(
                {
                    "sha256": source_hash,
                    "bytes": source.stat().st_size,
                }
            )

        records.append(record)

    manifest = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "files": records,
    }

    _atomic_write_json(
        archive_dir / "manifest.json",
        manifest,
    )

    return manifest


def _validate_unique_counted_ids(
    counted_ids: Any,
    expected_count: int,
) -> list[str]:
    if not isinstance(
        counted_ids,
        list,
    ):
        raise PolicyEpochMigrationError("COUNTED_TRADE_IDS_NOT_LIST")

    if len(counted_ids) != len(set(counted_ids)):
        raise PolicyEpochMigrationError("COUNTED_TRADE_IDS_DUPLICATE")

    if len(counted_ids) != expected_count:
        raise PolicyEpochMigrationError("CERTIFICATION_COUNTER_INCOHERENT")

    return [str(value) for value in counted_ids]


def migrate_index_bundle(
    *,
    market: str,
    state_path: Path,
    ledger_paths: list[Path],
    archive_dir: Path,
    expected_old_strategy_version: str,
    expected_old_certification_epoch: str,
    new_strategy_version: str,
    new_certification_epoch: str,
) -> dict[str, Any]:
    """Archive an index epoch, reset live ledgers, and start new certification authority."""

    market = market.upper()

    state = _load_json(state_path)

    if state.get("market") != market:
        raise PolicyEpochMigrationError("INDEX_MARKET_MISMATCH")

    active = state.get("active_trades") or []

    if active:
        raise PolicyEpochMigrationError("INDEX_ACTIVE_TRADES_PRESENT")

    old_strategy = state.get("strategy_version")
    old_epoch = state.get("certification_epoch")

    if not old_strategy or not old_epoch:
        raise PolicyEpochMigrationError("INDEX_OLD_POLICY_AUTHORITY_MISSING")

    if (
        old_strategy != expected_old_strategy_version
        or old_epoch != expected_old_certification_epoch
    ):
        raise PolicyEpochMigrationError("INDEX_UNEXPECTED_OLD_POLICY_AUTHORITY")

    if old_strategy == new_strategy_version and old_epoch == new_certification_epoch:
        raise PolicyEpochMigrationError("INDEX_ALREADY_TARGET_POLICY")

    counter = int(
        state.get(
            "certification_counter",
            0,
        )
        or 0
    )

    wins = int(
        state.get(
            "certification_wins",
            0,
        )
        or 0
    )

    losses = int(
        state.get(
            "certification_losses",
            0,
        )
        or 0
    )

    if wins + losses != counter:
        raise PolicyEpochMigrationError("INDEX_WIN_LOSS_COUNTER_INCOHERENT")

    counted_ids = (
        state.get(
            "counted_trade_ids",
            [],
        )
        or []
    )

    _validate_unique_counted_ids(
        counted_ids,
        counter,
    )

    manifest = _archive_exact_boundary(
        [
            state_path,
            *ledger_paths,
        ],
        archive_dir,
    )

    for ledger_path in ledger_paths:
        _atomic_reset_file(ledger_path)

    migrated = deepcopy(state)

    migrated["strategy_version"] = new_strategy_version

    migrated["certification_epoch"] = new_certification_epoch

    migrated["certification_counter"] = 0

    migrated["certification_wins"] = 0

    migrated["certification_losses"] = 0

    migrated["counted_trade_ids"] = []

    migrated["diversity_state"] = deepcopy(EMPTY_EQUITY_DIVERSITY_STATE)

    _atomic_write_json(
        state_path,
        migrated,
    )

    return {
        "status": "MIGRATED",
        "market": market,
        "from_strategy_version": old_strategy,
        "from_certification_epoch": old_epoch,
        "to_strategy_version": new_strategy_version,
        "to_certification_epoch": new_certification_epoch,
        "archived_certification_counter": counter,
        "archive_dir": str(archive_dir),
        "archive_manifest": manifest,
    }


def migrate_mcx_bundle(
    *,
    product: str,
    state_path: Path,
    version_path: Path,
    ledger_paths: list[Path],
    archive_dir: Path,
    expected_old_strategy_version: str,
    expected_old_epoch: str,
    new_strategy_version: str,
    new_epoch: str,
    certification_eligible: bool,
) -> dict[str, Any]:
    """Archive an MCX epoch, reset live ledgers, and initialize a fresh campaign."""

    product = product.upper()

    state = _load_json(state_path)

    authority = _load_json(version_path)

    if state.get("product") != product:
        raise PolicyEpochMigrationError("MCX_PRODUCT_MISMATCH")

    if authority.get("product") not in (
        None,
        product,
    ):
        raise PolicyEpochMigrationError("MCX_AUTHORITY_PRODUCT_MISMATCH")

    if state.get("active_position"):
        raise PolicyEpochMigrationError("MCX_ACTIVE_POSITION_PRESENT")

    old_strategy = state.get("strategy_version")
    old_epoch = state.get("epoch")

    if not old_strategy or not old_epoch:
        raise PolicyEpochMigrationError("MCX_OLD_POLICY_AUTHORITY_MISSING")

    if authority.get("strategy_version") != old_strategy or authority.get("epoch") != old_epoch:
        raise PolicyEpochMigrationError("MCX_STATE_AUTHORITY_MISMATCH")

    if old_strategy != expected_old_strategy_version or old_epoch != expected_old_epoch:
        raise PolicyEpochMigrationError("MCX_UNEXPECTED_OLD_POLICY_AUTHORITY")

    if old_strategy == new_strategy_version and old_epoch == new_epoch:
        raise PolicyEpochMigrationError("MCX_ALREADY_TARGET_POLICY")

    countable = int(
        state.get(
            "t1_hit_wins",
            0,
        )
        or 0
    ) + int(
        state.get(
            "sl_losses",
            0,
        )
        or 0
    )

    counted_ids = (
        state.get(
            "_counted_trade_ids",
            [],
        )
        or []
    )

    _validate_unique_counted_ids(
        counted_ids,
        countable,
    )

    manifest = _archive_exact_boundary(
        [
            state_path,
            version_path,
            *ledger_paths,
        ],
        archive_dir,
    )

    for ledger_path in ledger_paths:
        _atomic_reset_file(ledger_path)

    now = datetime.now(UTC).isoformat()

    fresh_state = {
        "product": product,
        "epoch": new_epoch,
        "strategy_version": new_strategy_version,
        "certification_eligible": bool(certification_eligible),
        "starting_capital": state.get(
            "starting_capital",
            100000,
        ),
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "t1_hit_wins": 0,
        "sl_losses": 0,
        "total_pnl": 0.0,
        "active_position": None,
        "completed_trades": [],
        "_counted_trade_ids": [],
        "created_at": now,
    }

    fresh_authority = {
        "product": product,
        "strategy_version": new_strategy_version,
        "epoch": new_epoch,
        "certification_eligible": bool(certification_eligible),
        "frozen_at": now,
        "note": "Version frozen for the duration of this certification epoch.",
    }

    # Cross-file atomicity is impossible, but each file is replaced
    # atomically. Any interruption between these writes produces an epoch
    # mismatch, which the MCX runtime already treats as fail-closed.
    _atomic_write_json(
        version_path,
        fresh_authority,
    )

    _atomic_write_json(
        state_path,
        fresh_state,
    )

    return {
        "status": "MIGRATED",
        "product": product,
        "from_strategy_version": old_strategy,
        "from_epoch": old_epoch,
        "to_strategy_version": new_strategy_version,
        "to_epoch": new_epoch,
        "archived_countable_trades": countable,
        "archive_dir": str(archive_dir),
        "archive_manifest": manifest,
    }
