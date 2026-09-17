"""Immutable, side-effect-free paper-trade candidate contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import math
from typing import Any, Mapping
from uuid import uuid4
from zoneinfo import ZoneInfo


class PaperCandidateValidationError(ValueError):
    """Raised when a paper candidate lacks execution-safe identity or plan data."""


def _timestamp(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime):
        raise PaperCandidateValidationError("Timestamp must be ISO-8601 compatible.")
    if value.tzinfo is None:
        raise PaperCandidateValidationError("Timestamp must be timezone-aware.")
    return value.astimezone(ZoneInfo("Asia/Kolkata"))


def _positive(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise PaperCandidateValidationError(f"{name} must be positive and finite.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PaperCandidateValidationError(f"{name} must be numeric.") from exc
    if not math.isfinite(number) or number <= 0:
        raise PaperCandidateValidationError(f"{name} must be positive and finite.")
    return number


@dataclass(frozen=True, slots=True)
class PaperTradeCandidateV1:
    snapshot_id: str
    decision_id: str
    symbol: str
    exchange: str
    action: str
    option_type: str
    tradingsymbol: str | None
    instrument_token: str | None
    entry: float
    stop_loss: float
    targets: tuple[float, ...]
    quantity: float
    created_at: datetime | str
    expires_at: datetime | str
    authorization_status: str
    execution_status: str
    candidate_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: str = "paper_trade_candidate.v1"
    position_side: str | None = None
    lots: float | None = None
    lot_size: float | None = None
    risk_amount: float | None = None
    risk_reward: float | None = None
    approval_required: bool = True
    approved: bool = False
    data_health_status: str = "UNKNOWN"
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("candidate_id", "snapshot_id", "decision_id", "symbol", "exchange"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise PaperCandidateValidationError(f"{name} is required.")
        if self.schema_version != "paper_trade_candidate.v1":
            raise PaperCandidateValidationError("Unsupported schema version.")
        action = str(self.action).upper()
        option_type = str(self.option_type).upper()
        if action not in {"BUY", "SELL"}:
            raise PaperCandidateValidationError("action must be BUY or SELL.")
        if option_type not in {"CE", "PE"}:
            raise PaperCandidateValidationError("option_type must be CE or PE.")
        position_side = ("LONG" if action == "BUY" else "SHORT") if self.position_side is None else self.position_side
        if position_side not in {"LONG", "SHORT"}:
            raise PaperCandidateValidationError("position_side must be LONG or SHORT.")
        if action == "BUY" and position_side != "LONG":
            raise PaperCandidateValidationError("BUY candidates must use LONG position_side.")
        if action == "SELL" and position_side == "LONG" and option_type != "PE":
            raise PaperCandidateValidationError("SELL LONG candidates require PE option_type.")
        if not any(isinstance(value, str) and value.strip() for value in (self.tradingsymbol, self.instrument_token)):
            raise PaperCandidateValidationError("tradingsymbol or instrument_token is required.")
        created_at, expires_at = _timestamp(self.created_at), _timestamp(self.expires_at)
        if expires_at <= created_at:
            raise PaperCandidateValidationError("expires_at must be after created_at.")
        entry, stop_loss = _positive(self.entry, "entry"), _positive(self.stop_loss, "stop_loss")
        targets = tuple(_positive(value, "target") for value in self.targets)
        if not targets:
            raise PaperCandidateValidationError("At least one positive target is required.")
        if position_side == "LONG":
            if not stop_loss < entry:
                raise PaperCandidateValidationError("LONG stop_loss must be below entry.")
            if any(target <= entry for target in targets) or any(right <= left for left, right in zip(targets, targets[1:])):
                raise PaperCandidateValidationError("LONG targets must be above entry and strictly increasing.")
        elif not stop_loss > entry:
            raise PaperCandidateValidationError("SHORT stop_loss must be above entry.")
        elif any(target >= entry for target in targets) or any(right >= left for left, right in zip(targets, targets[1:])):
            raise PaperCandidateValidationError("SHORT targets must be below entry and strictly decreasing.")
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "option_type", option_type)
        object.__setattr__(self, "position_side", position_side)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "entry", entry)
        object.__setattr__(self, "stop_loss", stop_loss)
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "quantity", _positive(self.quantity, "quantity"))
        for name in ("lots", "lot_size", "risk_amount", "risk_reward"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _positive(value, name))
        try:
            json.dumps(self.metadata, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise PaperCandidateValidationError("metadata must be JSON-serializable.") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "snapshot_id": self.snapshot_id,
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "action": self.action,
            "option_type": self.option_type,
            "position_side": self.position_side,
            "tradingsymbol": self.tradingsymbol,
            "instrument_token": self.instrument_token,
            "entry": self.entry,
            "stop_loss": self.stop_loss,
            "targets": list(self.targets),
            "quantity": self.quantity,
            "lots": self.lots,
            "lot_size": self.lot_size,
            "risk_amount": self.risk_amount,
            "risk_reward": self.risk_reward,
            "authorization_status": self.authorization_status,
            "execution_status": self.execution_status,
            "approval_required": self.approval_required,
            "approved": self.approved,
            "data_health_status": self.data_health_status,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def semantic_dict(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("candidate_id")
        value.pop("created_at")
        return value

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PaperTradeCandidateV1":
        return cls(
            snapshot_id=payload.get("snapshot_id", ""),
            decision_id=payload.get("decision_id", ""),
            symbol=payload.get("symbol", ""), exchange=payload.get("exchange", ""),
            action=payload.get("action", ""), option_type=payload.get("option_type", ""),
            tradingsymbol=payload.get("tradingsymbol"), instrument_token=payload.get("instrument_token"),
            entry=payload.get("entry"), stop_loss=payload.get("stop_loss"),
            targets=tuple(payload.get("targets", ())), quantity=payload.get("quantity"),
            created_at=payload.get("created_at"), expires_at=payload.get("expires_at"),
            authorization_status=payload.get("authorization_status", ""),
            execution_status=payload.get("execution_status", ""),
            candidate_id=payload.get("candidate_id", str(uuid4())),
            schema_version=payload.get("schema_version", "paper_trade_candidate.v1"),
            position_side=payload.get("position_side"),
            lots=payload.get("lots"), lot_size=payload.get("lot_size"),
            risk_amount=payload.get("risk_amount"), risk_reward=payload.get("risk_reward"),
            approval_required=bool(payload.get("approval_required", True)),
            approved=bool(payload.get("approved", False)),
            data_health_status=payload.get("data_health_status", "UNKNOWN"),
            warnings=tuple(payload.get("warnings", ())), errors=tuple(payload.get("errors", ())),
            metadata=payload.get("metadata", {}),
        )
