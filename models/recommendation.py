from dataclasses import dataclass


@dataclass
class Recommendation:

    action: str

    confidence: float

    strategy: str

    entry: float

    stop_loss: float

    target1: float

    target2: float

    reason: list[str]