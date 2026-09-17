"""Initial deterministic policy for option-chain structural quality."""
from __future__ import annotations

from dataclasses import dataclass, fields
import math

from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES


_BEHAVIORS = ("BLOCK", "WARN", "ALLOW")


def _finite(value: object, *, positive: bool = False) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and (value > 0 if positive else value >= 0)
    )


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _primitive(value: object) -> object:
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class OptionChainPolicyV1:
    """Paper-only policy; it contains no intelligence or market recommendations."""

    policy_name: str
    supported_markets: tuple[tuple[str, str], ...]
    maximum_age_seconds: float
    future_tolerance_seconds: float
    minimum_total_strikes: int
    minimum_complete_pairs: int
    minimum_completeness_ratio: float
    incomplete_behavior: str = "BLOCK"
    missing_side_behavior: str = "WARN"
    crossed_market_behavior: str = "BLOCK"
    duplicate_strike_behavior: str = "BLOCK"
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "option_chain_policy.v1"

    def __post_init__(self) -> None:
        if not isinstance(self.policy_name, str) or not self.policy_name.strip():
            raise ValueError("policy_name must be a non-empty string.")
        if self.supported_markets != SUPPORTED_MARKET_IDENTITIES:
            raise ValueError("supported_markets must be the exact canonical four-market universe.")
        if not _finite(self.maximum_age_seconds, positive=True) or not _finite(self.future_tolerance_seconds):
            raise ValueError("Policy age tolerances must be finite and valid.")
        if not _integer(self.minimum_total_strikes) or not _integer(self.minimum_complete_pairs):
            raise ValueError("Policy minimum counts must be non-negative integers.")
        if not _finite(self.minimum_completeness_ratio) or not 0.0 <= self.minimum_completeness_ratio <= 1.0:
            raise ValueError("minimum_completeness_ratio must be from zero through one.")
        if any(value not in _BEHAVIORS for value in (
            self.incomplete_behavior, self.missing_side_behavior,
            self.crossed_market_behavior, self.duplicate_strike_behavior,
        )):
            raise ValueError("Option-chain policy behaviors must be BLOCK, WARN, or ALLOW.")
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("Option-chain policy is paper-only.")
        if self.schema_version != "option_chain_policy.v1":
            raise ValueError("Invalid option-chain policy schema version.")

    def to_dict(self) -> dict[str, object]:
        return {field.name: _primitive(getattr(self, field.name)) for field in fields(self)}


DEFAULT_OPTION_CHAIN_POLICY = OptionChainPolicyV1(
    policy_name="INITIAL_CANONICAL_OPTION_CHAIN_POLICY",
    supported_markets=SUPPORTED_MARKET_IDENTITIES,
    maximum_age_seconds=300.0,
    future_tolerance_seconds=5.0,
    minimum_total_strikes=10,
    minimum_complete_pairs=5,
    minimum_completeness_ratio=0.50,
    incomplete_behavior="BLOCK",
    missing_side_behavior="WARN",
    crossed_market_behavior="BLOCK",
    duplicate_strike_behavior="BLOCK",
    execution_mode="PAPER",
    live_execution_eligible=False,
)
