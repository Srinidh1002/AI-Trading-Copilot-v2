"""Atomic PAPER closure journal and deterministic capital release."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from services.contracts.active_paper_position_v1 import (
    ActivePaperPositionV1,
)
from services.contracts.paper_trade_finalization_v1 import (
    PaperTradeClosureJournalEntryV1,
    PaperTradeFinalizationResultV1,
)


class JsonPaperTradeJournalRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def list_all(
        self,
    ) -> tuple[PaperTradeClosureJournalEntryV1, ...]:
        if not self._path.exists():
            return ()
        try:
            raw = json.loads(
                self._path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("invalid PAPER trade journal") from exc
        if not isinstance(raw, list):
            raise ValueError("invalid PAPER trade journal")
        return tuple(
            self._decode(item)
            for item in sorted(
                raw,
                key=lambda item: item["journal_entry_id"],
            )
        )

    def get_by_closure_id(
        self,
        closure_id: str,
    ) -> PaperTradeClosureJournalEntryV1 | None:
        for item in self.list_all():
            if item.closure_id == closure_id:
                return item
        return None

    def append(
        self,
        entry: PaperTradeClosureJournalEntryV1,
    ) -> PaperTradeClosureJournalEntryV1:
        if type(entry) is not PaperTradeClosureJournalEntryV1:
            raise TypeError("entry")
        entries = {
            item.journal_entry_id: item
            for item in self.list_all()
        }
        for current in entries.values():
            if current.closure_id == entry.closure_id:
                if current != entry:
                    raise ValueError("closure_id conflict")
                return current
            if current.position_id == entry.position_id:
                raise ValueError("position already journaled")
        entries[entry.journal_entry_id] = entry
        self._write_atomic(
            tuple(entries[key] for key in sorted(entries))
        )
        return entry

    def _write_atomic(
        self,
        entries: tuple[PaperTradeClosureJournalEntryV1, ...],
    ) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(self._path.suffix + ".tmp")
        payload = []
        for entry in entries:
            item = asdict(entry)
            item["opened_at"] = entry.opened_at.isoformat()
            item["closed_at"] = entry.closed_at.isoformat()
            item["processed_event_ids"] = list(
                entry.processed_event_ids
            )
            item["warnings"] = list(entry.warnings)
            payload.append(item)
        temp.write_text(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        os.replace(temp, self._path)

    @staticmethod
    def _decode(
        value: dict[str, object],
    ) -> PaperTradeClosureJournalEntryV1:
        if not isinstance(value, dict):
            raise ValueError("invalid journal entry")
        decoded = dict(value)
        decoded.pop("SCHEMA_VERSION", None)
        decoded["opened_at"] = datetime.fromisoformat(
            str(decoded["opened_at"])
        )
        decoded["closed_at"] = datetime.fromisoformat(
            str(decoded["closed_at"])
        )
        decoded["processed_event_ids"] = tuple(
            decoded.get("processed_event_ids", ())
        )
        decoded["warnings"] = tuple(
            decoded.get("warnings", ())
        )
        return PaperTradeClosureJournalEntryV1(**decoded)


def finalize_closed_paper_trade(
    *,
    finalization_result_id: str,
    closure_id: str,
    journal_entry_id: str,
    finalized_at: datetime,
    closure_reason: str,
    final_exit_price: float,
    position: ActivePaperPositionV1,
    journal_repository: JsonPaperTradeJournalRepository,
) -> PaperTradeFinalizationResultV1:
    if type(position) is not ActivePaperPositionV1:
        raise TypeError("position")
    if type(journal_repository) is not JsonPaperTradeJournalRepository:
        raise TypeError("journal_repository")
    if position.lifecycle_state != "CLOSED":
        raise ValueError("position must be CLOSED")
    if position.remaining_quantity != 0 or position.remaining_lots != 0:
        raise ValueError("closed position retains quantity")
    if finalized_at < position.updated_at:
        raise ValueError("finalized_at precedes position")

    existing = journal_repository.get_by_closure_id(closure_id)
    if existing is not None:
        if existing.position_id != position.position_id:
            raise ValueError("closure_id conflict")
        return PaperTradeFinalizationResultV1(
            finalization_result_id=finalization_result_id,
            closure_id=closure_id,
            position_id=position.position_id,
            finalized_at=finalized_at,
            status="FINALIZED",
            released_capital=existing.released_capital,
            released_risk=existing.released_risk,
            journal_entry=existing,
            warnings=("IDEMPOTENT_FINALIZATION_REPLAY",),
        )

    entry = PaperTradeClosureJournalEntryV1(
        journal_entry_id=journal_entry_id,
        closure_id=closure_id,
        position_id=position.position_id,
        recommendation_id=position.recommendation_id,
        reservation_result_id=position.reservation_result_id,
        fill_result_id=position.fill_result_id,
        contract=position.contract,
        underlying_symbol=position.underlying_symbol,
        exchange=position.exchange,
        option_right=position.option_right,
        opened_at=position.opened_at,
        closed_at=position.updated_at,
        closure_reason=closure_reason,
        initial_quantity=position.initial_quantity,
        closed_quantity=position.initial_quantity,
        entry_price=position.entry_price,
        final_exit_price=final_exit_price,
        realized_pnl=position.realized_pnl,
        released_capital=position.reserved_capital,
        released_risk=position.maximum_loss,
        processed_event_ids=position.processed_event_ids,
        warnings=position.warnings,
    )
    persisted = journal_repository.append(entry)

    return PaperTradeFinalizationResultV1(
        finalization_result_id=finalization_result_id,
        closure_id=closure_id,
        position_id=position.position_id,
        finalized_at=finalized_at,
        status="FINALIZED",
        released_capital=position.reserved_capital,
        released_risk=position.maximum_loss,
        journal_entry=persisted,
    )
