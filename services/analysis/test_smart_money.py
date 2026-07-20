from pprint import pprint
import time

from services.market.option_market import OptionMarket
from services.options.option_flow_engine import OptionFlowEngine
from services.options.snapshot_manager import SnapshotManager
from services.options.oi_change_engine import OIChangeEngine
from services.analysis.smart_money_engine import SmartMoneyEngine

market = OptionMarket()

manager = SnapshotManager()

print("Snapshot 1")

flow = OptionFlowEngine.analyze(
    market.chain_quotes(
        "NIFTY",
        24346.7,
        levels=10,
    )
)

manager.update(flow)

time.sleep(30)

print("Snapshot 2")

flow = OptionFlowEngine.analyze(
    market.chain_quotes(
        "NIFTY",
        24346.7,
        levels=10,
    )
)

manager.update(flow)

changes = OIChangeEngine.analyze(
    manager.get_previous(),
    manager.get_current(),
)

summary = SmartMoneyEngine.analyze(
    manager.get_current(),
    changes,
)

pprint(summary)