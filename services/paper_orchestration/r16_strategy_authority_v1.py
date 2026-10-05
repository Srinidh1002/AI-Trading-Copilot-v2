"""R16 selector-strategy authority and activation gate.

The R16 parent selector materially changes entry selection relative to the
independent R15 index workers.  It therefore has a distinct strategy identity,
state namespace, and explicit activation authority.  The default is SHADOW.

This module does not start workers or place/submit orders.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from services.paper_orchestration.process_lock_v2 import lock_available

R16_STRATEGY_VERSION = "R16_TWO_MARKET_PARENT_V1"
R16_CERTIFICATION_EPOCH = "R16_INDEX_PARENT_CERT_V1"
R16_STATE_NAMESPACE = "data/paper_trading/r16_two_market_parent"
R16_ACTIVATION_SCHEMA = "r16_selector_activation.v1"


@dataclass(frozen=True, slots=True)
class R16SelectorActivationStatusV1:
    ready: bool
    mode: str
    strategy_version: str
    certification_epoch: str
    paper_entry_authorized: bool
    live_execution_authorized: bool
    broker_order_submission_authorized: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.mode not in {"SHADOW_ONLY", "PAPER_ENTRY"}:
            raise ValueError("mode")
        if self.strategy_version != R16_STRATEGY_VERSION:
            raise ValueError("strategy_version")
        if self.certification_epoch != R16_CERTIFICATION_EPOCH:
            raise ValueError("certification_epoch")
        if self.live_execution_authorized or self.broker_order_submission_authorized:
            raise ValueError("R16 activation is PAPER-only")
        if self.ready != (
            self.mode == "PAPER_ENTRY"
            and self.paper_entry_authorized
            and not self.blockers
        ):
            raise ValueError("ready")
        if self.mode == "SHADOW_ONLY" and self.paper_entry_authorized:
            raise ValueError("shadow cannot authorize entry")


def activation_manifest_path(repo_root: str | Path) -> Path:
    return (
        Path(repo_root).resolve()
        / R16_STATE_NAMESPACE
        / "activation.json"
    )


def build_shadow_activation_manifest() -> dict:
    return {
        "schema_version": R16_ACTIVATION_SCHEMA,
        "strategy_version": R16_STRATEGY_VERSION,
        "certification_epoch": R16_CERTIFICATION_EPOCH,
        "mode": "SHADOW_ONLY",
        "paper_entry_authorized": False,
        "live_execution_authorized": False,
        "broker_order_submission_authorized": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def read_activation_manifest(repo_root: str | Path) -> dict | None:
    path = activation_manifest_path(repo_root)
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("R16_ACTIVATION_SCHEMA_INVALID")
    return value


def _validate_manifest(value: dict | None) -> tuple[str, bool, list[str]]:
    blockers: list[str] = []

    if value is None:
        return "SHADOW_ONLY", False, ["R16_ACTIVATION_MANIFEST_MISSING"]

    if value.get("schema_version") != R16_ACTIVATION_SCHEMA:
        blockers.append("R16_ACTIVATION_SCHEMA_MISMATCH")
    if value.get("strategy_version") != R16_STRATEGY_VERSION:
        blockers.append("R16_STRATEGY_VERSION_MISMATCH")
    if value.get("certification_epoch") != R16_CERTIFICATION_EPOCH:
        blockers.append("R16_CERTIFICATION_EPOCH_MISMATCH")

    mode = str(value.get("mode") or "SHADOW_ONLY").strip().upper()
    if mode not in {"SHADOW_ONLY", "PAPER_ENTRY"}:
        blockers.append("R16_ACTIVATION_MODE_INVALID")
        mode = "SHADOW_ONLY"

    paper = value.get("paper_entry_authorized") is True
    live = value.get("live_execution_authorized") is True
    broker = value.get("broker_order_submission_authorized") is True

    if live:
        blockers.append("LIVE_EXECUTION_PROHIBITED")
    if broker:
        blockers.append("BROKER_ORDER_SUBMISSION_PROHIBITED")
    if mode == "PAPER_ENTRY" and not paper:
        blockers.append("PAPER_ENTRY_AUTHORIZATION_REQUIRED")
    if mode == "SHADOW_ONLY" and paper:
        blockers.append("SHADOW_ENTRY_AUTHORIZATION_CONFLICT")

    return mode, paper, blockers


def evaluate_r16_selector_activation(
    *,
    repo_root: str | Path,
    incumbent_runtime_root: str | Path | None = None,
) -> R16SelectorActivationStatusV1:
    """Read-only activation verdict.

    If incumbent_runtime_root is supplied, its canonical supervisor guard must
    be free before R16 PAPER entry can become ready.  Shadow observation does
    not require ownership of that lock.
    """

    manifest = read_activation_manifest(repo_root)
    mode, paper, blockers = _validate_manifest(manifest)

    if incumbent_runtime_root is not None and mode == "PAPER_ENTRY":
        incumbent_lock = (
            Path(incumbent_runtime_root).resolve()
            / "logs"
            / "supervisor"
            / ".lock"
        )
        if not lock_available(
            incumbent_lock,
            role="R16_INCUMBENT_PROBE",
        ):
            blockers.append("INCUMBENT_PAPER_SUPERVISOR_ACTIVE")

    # A PAPER-entry activation starts a fresh namespace. It must not inherit an
    # already-counted R15 state file or historical index state by alias.
    namespace = Path(repo_root).resolve() / R16_STATE_NAMESPACE
    if mode == "PAPER_ENTRY":
        legacy_names = (
            "nifty_experimental.json",
            "sensex_experimental.json",
        )
        for name in legacy_names:
            if (namespace / name).exists():
                blockers.append(
                    f"R16_NAMESPACE_CONTAINS_LEGACY_STATE:{name}"
                )

    unique = tuple(dict.fromkeys(blockers))
    ready = mode == "PAPER_ENTRY" and paper and not unique

    return R16SelectorActivationStatusV1(
        ready=ready,
        mode=mode,
        strategy_version=R16_STRATEGY_VERSION,
        certification_epoch=R16_CERTIFICATION_EPOCH,
        paper_entry_authorized=paper,
        live_execution_authorized=False,
        broker_order_submission_authorized=False,
        blockers=unique,
    )
