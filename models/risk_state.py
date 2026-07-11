from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RiskState:
    # Existing risk-engine fields
    approved: Optional[bool] = None
    position_size: int = 0
    risk_amount: float = 0.0
    warnings: list[str] = field(
        default_factory=list
    )

    # Shared field
    decision: str = "REJECTED"

    # New lot-based risk fields
    allowed: Optional[bool] = None
    capital: float = 0.0
    risk_percent: float = 0.0
    maximum_risk_amount: float = 0.0
    entry_price: float = 0.0
    stop_loss_price: float = 0.0
    target_price: float = 0.0
    risk_per_unit: float = 0.0
    reward_per_unit: float = 0.0
    risk_reward_ratio: float = 0.0
    lot_size: int = 0
    lots: int = 0
    quantity: int = 0
    required_capital: float = 0.0
    estimated_maximum_loss: float = 0.0

    reasons: list[str] = field(
        default_factory=list
    )