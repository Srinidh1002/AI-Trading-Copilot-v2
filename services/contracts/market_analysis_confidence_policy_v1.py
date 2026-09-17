"""Versioned shadow policy: no unapproved numerical deductions are introduced."""
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class MarketAnalysisConfidencePolicyV1:
    policy_id: str = "market-analysis-confidence-shadow"
    policy_version: str = "market_analysis_confidence_policy.v1.shadow"
    counted_source_components: tuple[str, ...] = ("candidate_policy",)
    grouped_pillars_counted: bool = False
    quality_penalty_rules: tuple[str, ...] = ("HARD_BLOCK_REQUIRED_NONREADY",)
    contradiction_penalty_rules: tuple[str, ...] = ("HARD_BLOCK_CONTRADICTION",)
    suitability_penalty_rules: tuple[str, ...] = ("HARD_BLOCK_SESSION_OR_REGIME",)
    confidence_floor: float = 0.0
    confidence_ceiling: float = 100.0
    neutral_tolerance: float = 0.0
    minimum_directional_evidence: int = 1
    rounding_decimals: int = 6
    hard_block_zeroes_output: bool = True
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    def __post_init__(self):
        if self.policy_id != "market-analysis-confidence-shadow" or self.policy_version != "market_analysis_confidence_policy.v1.shadow" or self.counted_source_components != ("candidate_policy",) or self.grouped_pillars_counted or self.confidence_floor != 0.0 or self.confidence_ceiling != 100.0 or self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("immutable shadow policy")
