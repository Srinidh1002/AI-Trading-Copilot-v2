from pprint import pprint
import time

from services.market.option_market import OptionMarket
from services.options.option_flow_engine import OptionFlowEngine
from services.options.snapshot_manager import SnapshotManager
from services.options.oi_change_engine import OIChangeEngine

market = OptionMarket()
manager = SnapshotManager()

print("\nFetching Snapshot 1...\n")

chain = market.chain_quotes(
    "NIFTY",
    24346.7,
    levels=10,
)

flow = OptionFlowEngine.analyze(chain)

manager.update(flow)

print("Waiting 30 seconds...\n")

time.sleep(30)

print("Fetching Snapshot 2...\n")

chain = market.chain_quotes(
    "NIFTY",
    24346.7,
    levels=10,
)

flow = OptionFlowEngine.analyze(chain)

manager.update(flow)

changes = OIChangeEngine.analyze(
    manager.get_previous(),
    manager.get_current(),
)

pprint(changes)