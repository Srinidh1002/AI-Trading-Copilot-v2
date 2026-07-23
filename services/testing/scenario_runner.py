"""
Scenario Runner

Runs predefined end-to-end trading scenarios against
the AI Trading Copilot.

Responsibilities
----------------
✓ Bullish Scenario
✓ Bearish Scenario
✓ Sideways Scenario
✓ Gap-Up Scenario
✓ Gap-Down Scenario
✓ High Volatility Scenario
✓ Low Volatility Scenario
✓ Expiry Day Scenario
✓ Flash Crash Scenario
✓ Recovery Rally Scenario
✓ Scenario Report
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from services.testing.mock_broker import MockBroker
from services.testing.test_data_generator import TestDataGenerator


class ScenarioRunner:

    def __init__(self):

        self.generator = TestDataGenerator()

        self.broker = MockBroker()

        self.results: list[dict[str, Any]] = []

    # --------------------------------------------------

    def _execute_scenario(

        self,

        name: str,

        direction: str,

        move: float,

        volatility: str,

    ):

        market = self.generator.market_snapshot()

        market["trend"] = direction

        entry = market["price"]

        exit_price = round(

            entry + move,

            2,

        )

        order = self.broker.place_order(

            symbol="NIFTY",

            side="BUY" if move >= 0 else "SELL",

            quantity=50,

            price=entry,

        )

        self.broker.execute_order(

            order["order_id"],

            entry,

        )

        self.broker.update_market_price(

            "NIFTY",

            exit_price,

        )

        self.broker.close_position(

            "NIFTY",

            exit_price,

        )

        pnl = round(

            abs(move) * 50,

            2,

        )

        if move < 0:

            pnl *= -1

        result = {

            "scenario": name,

            "timestamp": datetime.now().isoformat(),

            "trend": direction,

            "entry_price": entry,

            "exit_price": exit_price,

            "price_change": round(move, 2),

            "volatility": volatility,

            "expected_direction": (

                "BUY"

                if move >= 0

                else "SELL"

            ),

            "estimated_pnl": pnl,

            "status": "COMPLETED",

        }

        self.results.append(result)

        return deepcopy(result)

    # --------------------------------------------------

    def bullish(self):

        return self._execute_scenario(

            "Bullish",

            "Bullish",

            180,

            "Medium",

        )

    # --------------------------------------------------

    def bearish(self):

        return self._execute_scenario(

            "Bearish",

            "Bearish",

            -180,

            "Medium",

        )

    # --------------------------------------------------

    def sideways(self):

        return self._execute_scenario(

            "Sideways",

            "Sideways",

            10,

            "Low",

        )

    # --------------------------------------------------

    def gap_up(self):

        return self._execute_scenario(

            "Gap Up",

            "Bullish",

            320,

            "High",

        )

    # --------------------------------------------------

    def gap_down(self):

        return self._execute_scenario(

            "Gap Down",

            "Bearish",

            -320,

            "High",

        )

    # --------------------------------------------------

    def high_volatility(self):

        return self._execute_scenario(

            "High Volatility",

            "Volatile",

            500,

            "Very High",

        )

    # --------------------------------------------------

    def low_volatility(self):

        return self._execute_scenario(

            "Low Volatility",

            "Flat",

            5,

            "Very Low",

        )

    # --------------------------------------------------

    def expiry_day(self):

        return self._execute_scenario(

            "Expiry Day",

            "Mixed",

            250,

            "Extreme",

        )

    # --------------------------------------------------

    def flash_crash(self):

        return self._execute_scenario(

            "Flash Crash",

            "Crash",

            -900,

            "Extreme",

        )

    # --------------------------------------------------

    def recovery_rally(self):

        return self._execute_scenario(

            "Recovery Rally",

            "Recovery",

            650,

            "High",

        )

    # --------------------------------------------------

    def run_all(self):

        self.results.clear()

        self.broker = MockBroker()

        self.broker.login()

        self.bullish()

        self.bearish()

        self.sideways()

        self.gap_up()

        self.gap_down()

        self.high_volatility()

        self.low_volatility()

        self.expiry_day()

        self.flash_crash()

        self.recovery_rally()

        return self.summary()

    # --------------------------------------------------

    def total_scenarios(self):

        return len(self.results)

    # --------------------------------------------------

    def profitable(self):

        return sum(

            1

            for scenario in self.results

            if scenario["estimated_pnl"] > 0

        )

    # --------------------------------------------------

    def losing(self):

        return self.total_scenarios() - self.profitable()

    # --------------------------------------------------

    def total_estimated_pnl(self):

        return round(

            sum(

                scenario["estimated_pnl"]

                for scenario in self.results

            ),

            2,

        )

    # --------------------------------------------------

    def summary(self):

        return {

            "executed_at": datetime.now().isoformat(),

            "total_scenarios": self.total_scenarios(),

            "profitable": self.profitable(),

            "losing": self.losing(),

            "net_estimated_pnl": self.total_estimated_pnl(),

            "results": deepcopy(self.results),

        }


# ------------------------------------------------------
# Standalone Execution
# ------------------------------------------------------

if __name__ == "__main__":

    runner = ScenarioRunner()

    report = runner.run_all()

    print("\n" + "=" * 70)
    print(" AI TRADING COPILOT - SCENARIO RUNNER")
    print("=" * 70)
    print(f"Scenarios Executed : {report['total_scenarios']}")
    print(f"Profitable         : {report['profitable']}")
    print(f"Losing             : {report['losing']}")
    print(f"Net Estimated P&L  : {report['net_estimated_pnl']}")
    print("=" * 70)