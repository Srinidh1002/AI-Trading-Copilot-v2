from pprint import pprint
import time

from services.ai.trading_ai import TradingAI

ai = TradingAI()

print("Creating Initial Snapshot...")

ai.initialize()

time.sleep(30)

print("Running AI...\n")

report = ai.analyze()

pprint(report)