# trading_bot/core/state_machine.py
# Complete state machine

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List

from trading_bot.core.constants import MarketState, PositionStatus, ExitReason

logger = logging.getLogger(__name__)


@dataclass
class StateTransition:
    from_state: str
    to_state: str
    timestamp: str
    reason: str
    data: Dict[str, Any] = field(default_factory=dict)


class TradingStateMachine:
    def __init__(self):
        self.current_state = MarketState.BOOT
        self.previous_state = None
        self.transitions: List[StateTransition] = []
        self.state_data: Dict[str, Any] = {}
        self.is_running = False
        self.error_count = 0
        self.max_errors = 5
        logger.info(f"[STATE] Initialized: {self.current_state.value}")

    def transition_to(self, new_state: MarketState, reason: str, data: Optional[Dict[str, Any]] = None):
        if new_state == self.current_state:
            return
        transition = StateTransition(
            from_state=self.current_state.value,
            to_state=new_state.value,
            timestamp=datetime.now().isoformat(),
            reason=reason,
            data=data or {}
        )
        self.transitions.append(transition)
        self.previous_state = self.current_state
        self.current_state = new_state
        logger.info(f"[STATE] {transition.from_state} -> {transition.to_state} | {reason}")
        if data:
            self.state_data[new_state.value] = data

    def get_state(self) -> MarketState:
        return self.current_state

    def is_state(self, state: MarketState) -> bool:
        return self.current_state == state

    def can_transition_to(self, new_state: MarketState) -> bool:
        valid_transitions = {
            MarketState.BOOT: [MarketState.CONFIG_VALIDATION, MarketState.PRE_MARKET],
            MarketState.CONFIG_VALIDATION: [MarketState.PROVIDER_VALIDATION, MarketState.MARKET_CALENDAR_VALIDATION],
            MarketState.PROVIDER_VALIDATION: [MarketState.MARKET_CALENDAR_VALIDATION, MarketState.PRE_MARKET],
            MarketState.MARKET_CALENDAR_VALIDATION: [MarketState.RECONCILIATION, MarketState.PRE_MARKET],
            MarketState.RECONCILIATION: [MarketState.PRE_MARKET],
            MarketState.PRE_MARKET: [MarketState.WEBSOCKET_READY, MarketState.MARKET_OPEN],
            MarketState.WEBSOCKET_READY: [MarketState.MARKET_OPEN, MarketState.OBSERVING],
            MarketState.MARKET_OPEN: [MarketState.OBSERVING],
            MarketState.OBSERVING: [MarketState.SIGNAL_DETECTED, MarketState.CLOSED],
            MarketState.SIGNAL_DETECTED: [MarketState.SIGNAL_VALIDATED, MarketState.OBSERVING],
            MarketState.SIGNAL_VALIDATED: [MarketState.STRIKE_SELECTED, MarketState.OBSERVING],
            MarketState.STRIKE_SELECTED: [MarketState.OPTION_VALIDATED, MarketState.OBSERVING],
            MarketState.OPTION_VALIDATED: [MarketState.RISK_APPROVED, MarketState.OBSERVING],
            MarketState.RISK_APPROVED: [MarketState.ENTRY_PENDING, MarketState.OBSERVING],
            MarketState.ENTRY_PENDING: [MarketState.OPEN, MarketState.CLOSED],
            MarketState.OPEN: [MarketState.STOP_LOSS, MarketState.T1_REACHED, MarketState.T2_REACHED,
                               MarketState.T3_REACHED, MarketState.THESIS_INVALIDATION, MarketState.TIME_EXIT,
                               MarketState.DATA_RECOVERY, MarketState.FORCE_EXIT, MarketState.CLOSED],
            MarketState.STOP_LOSS: [MarketState.CLOSED],
            MarketState.T1_REACHED: [MarketState.T2_REACHED, MarketState.STOP_LOSS, MarketState.CLOSED],
            MarketState.T2_REACHED: [MarketState.T3_REACHED, MarketState.STOP_LOSS, MarketState.CLOSED],
            MarketState.T3_REACHED: [MarketState.CLOSED],
            MarketState.THESIS_INVALIDATION: [MarketState.CLOSED],
            MarketState.TIME_EXIT: [MarketState.CLOSED],
            MarketState.DATA_RECOVERY: [MarketState.OPEN, MarketState.CLOSED],
            MarketState.FORCE_EXIT: [MarketState.CLOSED],
            MarketState.CLOSED: [MarketState.RECONCILED, MarketState.OBSERVING],
            MarketState.RECONCILED: [MarketState.SESSION_END],
            MarketState.SESSION_END: []
        }
        if new_state not in valid_transitions.get(self.current_state, []):
            logger.warning(f"[STATE] Invalid transition: {self.current_state.value} -> {new_state.value}")
            return False
        return True

    def transition(self, new_state: MarketState, reason: str, data: Optional[Dict[str, Any]] = None) -> bool:
        if not self.can_transition_to(new_state):
            return False
        self.transition_to(new_state, reason, data)
        return True

    def reset(self):
        self.current_state = MarketState.BOOT
        self.previous_state = None
        self.transitions = []
        self.state_data = {}
        self.is_running = False
        logger.info("[STATE] Reset complete")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_state": self.current_state.value,
            "previous_state": self.previous_state.value if self.previous_state else None,
            "transition_count": len(self.transitions),
            "is_running": self.is_running,
            "error_count": self.error_count
        }
