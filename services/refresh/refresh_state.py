"""
Central Refresh State

Shared runtime cache used by all services.
"""

class RefreshState:

    def __init__(self):

        self.market_snapshot = None

        self.last_market_snapshot = 0

        self.option_chain = None

        self.last_option_chain = 0

        self.greeks = None

        self.last_greeks = 0

        self.decision = None

        self.last_decision = 0


refresh_state = RefreshState()