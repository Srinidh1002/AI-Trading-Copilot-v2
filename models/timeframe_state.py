from dataclasses import dataclass, field


@dataclass
class TimeframeState:
    overall_trend: str
    confidence: int
    alignment: str
    timeframe_results: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)