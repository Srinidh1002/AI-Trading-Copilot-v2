"""
Trading AI
"""


from services.market.option_market import OptionMarket
from services.options.option_flow_engine import OptionFlowEngine
from services.options.snapshot_manager import SnapshotManager
from services.options.oi_change_engine import OIChangeEngine
from services.options.market_structure_engine import MarketStructureEngine

from services.decision.master_decision_engine import MasterDecisionEngine
from services.risk.risk_engine import RiskEngine
from services.execution.trade_validator import TradeValidator
from services.execution.market_guard import MarketGuard
from services.ai.market_report_engine import MarketReportEngine


class TradingAI:

    def __init__(self):

        self.market = OptionMarket()

        self.snapshot = SnapshotManager()

    def initialize(
        self,
        symbol="NIFTY",
        spot=24346.7,
        levels=10,
    ):

        flow = OptionFlowEngine.analyze(
            self.market.chain_quotes(
                symbol,
                spot,
                levels,
            )
        )

        self.snapshot.update(flow)

    def analyze(
        self,
        symbol="NIFTY",
        spot=24346.7,
        levels=10,
    ):

        flow = OptionFlowEngine.analyze(
            self.market.chain_quotes(
                symbol,
                spot,
                levels,
            )
        )

        self.snapshot.update(flow)

        previous = self.snapshot.get_previous()

        current = self.snapshot.get_current()

        changes = OIChangeEngine.analyze(
            previous,
            current,
        )

        decision = MasterDecisionEngine.analyze(
            self.market.chain_quotes(
                symbol,
                spot,
                levels,
            ),
            changes,
        )

        risk = RiskEngine.analyze(
            decision,
            current,
            MarketStructureEngine.analyze(current),
        )

        validation = TradeValidator.validate(
            decision,
            risk,
        )

        guard = MarketGuard.evaluate(
            decision,
            risk,
            validation,
        )

        return MarketReportEngine.generate(
            decision,
            risk,
            validation,
            guard,
        )