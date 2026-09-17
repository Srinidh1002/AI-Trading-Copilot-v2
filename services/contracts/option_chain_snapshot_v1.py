"""Immutable normalized option-chain snapshot contract."""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime
import math

from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
from services.contracts.option_strike_row_v1 import OptionStrikeRowV1


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _messages(value: object) -> bool:
    return isinstance(value, tuple) and all(_text(item) for item in value)


def _primitive(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    if isinstance(value, OptionStrikeRowV1):
        return value.to_dict()
    return value


@dataclass(frozen=True, slots=True)
class OptionChainSnapshotV1:
    """One complete, supplied-record-only normalized option-chain snapshot."""

    option_chain_snapshot_id: str
    created_at: datetime
    underlying_symbol: str
    exchange: str
    expiry: date
    underlying_value: float | None
    strike_rows: tuple[OptionStrikeRowV1, ...]
    strike_count: int
    complete_pair_count: int
    call_only_count: int
    put_only_count: int
    minimum_strike: float | None
    maximum_strike: float | None
    source_timestamp: datetime
    provider_name: str
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "option_chain_snapshot.v1"

    def __post_init__(self) -> None:
        if not _text(self.option_chain_snapshot_id):
            raise ValueError("option_chain_snapshot_id must be a non-empty string.")
        if (self.underlying_symbol, self.exchange) not in SUPPORTED_MARKET_IDENTITIES:
            raise ValueError("Snapshot identity must be an exact supported market identity.")
        if not isinstance(self.expiry, date) or isinstance(self.expiry, datetime):
            raise ValueError("expiry must be a date.")
        if self.underlying_value is not None and not _positive_number(self.underlying_value):
            raise ValueError("underlying_value must be finite and greater than zero when supplied.")
        if not isinstance(self.strike_rows, tuple) or not all(isinstance(row, OptionStrikeRowV1) for row in self.strike_rows):
            raise ValueError("strike_rows must be a tuple of OptionStrikeRowV1 values.")
        if not all(_integer(value) for value in (self.strike_count, self.complete_pair_count, self.call_only_count, self.put_only_count)):
            raise ValueError("Snapshot counts must be non-negative integers.")
        if not all(_aware(value) for value in (self.created_at, self.source_timestamp)):
            raise ValueError("Snapshot timestamps must be timezone-aware.")
        if not _text(self.provider_name):
            raise ValueError("provider_name must be a non-empty string.")
        if not _messages(self.blockers) or not _messages(self.warnings):
            raise ValueError("blockers and warnings must be tuples of non-empty strings.")
        rows = self.strike_rows
        strikes = tuple(row.strike for row in rows)
        if tuple(sorted(strikes)) != strikes or len(set(strikes)) != len(strikes):
            raise ValueError("Snapshot strike rows must be strictly ascending and unique.")
        for row in rows:
            if (row.underlying_symbol, row.exchange, row.expiry) != (self.underlying_symbol, self.exchange, self.expiry):
                raise ValueError("Every strike row must match snapshot identity and expiry.")
        expected_complete = sum(row.call is not None and row.put is not None for row in rows)
        expected_call_only = sum(row.call is not None and row.put is None for row in rows)
        expected_put_only = sum(row.call is None and row.put is not None for row in rows)
        if (self.strike_count, self.complete_pair_count, self.call_only_count, self.put_only_count) != (
            len(rows), expected_complete, expected_call_only, expected_put_only,
        ):
            raise ValueError("Snapshot counts must reconcile exactly with strike rows.")
        if rows:
            if self.minimum_strike != strikes[0] or self.maximum_strike != strikes[-1]:
                raise ValueError("Snapshot minimum and maximum strikes must reconcile with rows.")
        elif self.minimum_strike is not None or self.maximum_strike is not None:
            raise ValueError("An empty snapshot uses None minimum and maximum strikes.")
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("Option-chain snapshot is paper-only.")
        if self.schema_version != "option_chain_snapshot.v1":
            raise ValueError("Invalid option-chain snapshot schema version.")

    def to_dict(self) -> dict[str, object]:
        return {field.name: _primitive(getattr(self, field.name)) for field in fields(self)}
