"""Immutable, non-directional quality result for an option-chain snapshot."""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime
import math

from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES


_STATUSES = (
    "VALID", "VALID_WITH_WARNINGS", "EMPTY", "STALE", "FUTURE", "INCOMPLETE",
    "MALFORMED", "UNSUPPORTED", "FAILED",
)
_BLOCKING_STATUSES = frozenset(_STATUSES) - {"VALID", "VALID_WITH_WARNINGS"}


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _messages(value: object) -> bool:
    return isinstance(value, tuple) and all(_text(item) for item in value)


def _primitive(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class OptionChainQualityResultV1:
    """Structural, freshness, and malformed-input status only."""

    option_chain_quality_result_id: str
    created_at: datetime
    option_chain_snapshot_id: str
    underlying_symbol: str
    exchange: str
    expiry: date
    quality_status: str
    age_seconds: float
    total_strikes: int
    complete_pair_count: int
    missing_call_count: int
    missing_put_count: int
    malformed_quote_count: int
    duplicate_strike_count: int
    completeness_ratio: float
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: str = "option_chain_quality_result.v1"

    def __post_init__(self) -> None:
        if not _text(self.option_chain_quality_result_id) or not _text(self.option_chain_snapshot_id):
            raise ValueError("Quality result identifiers must be non-empty strings.")
        if not _aware(self.created_at):
            raise ValueError("created_at must be timezone-aware.")
        if (self.underlying_symbol, self.exchange) not in SUPPORTED_MARKET_IDENTITIES:
            raise ValueError("Quality result identity must be an exact supported market identity.")
        if not isinstance(self.expiry, date) or isinstance(self.expiry, datetime):
            raise ValueError("expiry must be a date.")
        if self.quality_status not in _STATUSES:
            raise ValueError("Unsupported option-chain quality status.")
        if not isinstance(self.age_seconds, (int, float)) or isinstance(self.age_seconds, bool) or not math.isfinite(self.age_seconds):
            raise ValueError("age_seconds must be finite.")
        if not all(_integer(value) for value in (
            self.total_strikes, self.complete_pair_count, self.missing_call_count,
            self.missing_put_count, self.malformed_quote_count, self.duplicate_strike_count,
        )):
            raise ValueError("Quality counts must be non-negative integers.")
        if self.complete_pair_count + self.missing_call_count + self.missing_put_count != self.total_strikes:
            raise ValueError("Quality strike counts must reconcile exactly.")
        if (
            not isinstance(self.completeness_ratio, (int, float))
            or isinstance(self.completeness_ratio, bool)
            or not math.isfinite(self.completeness_ratio)
            or not 0.0 <= self.completeness_ratio <= 1.0
        ):
            raise ValueError("completeness_ratio must be a finite value from zero through one.")
        expected_ratio = self.complete_pair_count / self.total_strikes if self.total_strikes else 0.0
        if not math.isclose(float(self.completeness_ratio), expected_ratio, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("completeness_ratio must reconcile with quality counts.")
        if not _messages(self.blockers) or not _messages(self.warnings):
            raise ValueError("blockers and warnings must be tuples of non-empty strings.")
        if self.quality_status in _BLOCKING_STATUSES and not self.blockers:
            raise ValueError("Blocking quality statuses require blockers.")
        if self.quality_status == "VALID" and (self.blockers or self.warnings):
            raise ValueError("VALID quality has no blockers or warnings.")
        if self.quality_status == "VALID_WITH_WARNINGS" and (self.blockers or not self.warnings):
            raise ValueError("VALID_WITH_WARNINGS requires warnings and no blockers.")
        if self.schema_version != "option_chain_quality_result.v1":
            raise ValueError("Invalid option-chain quality result schema version.")

    def to_dict(self) -> dict[str, object]:
        return {field.name: _primitive(getattr(self, field.name)) for field in fields(self)}
