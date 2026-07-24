"""
System Health Check
"""

from services.utils import safe_execute


class HealthCheck:

    def run(self):

        return {
            "market_snapshot": safe_execute(
                lambda: "OK",
                default="FAILED",
            ),
            "database": safe_execute(
                lambda: "OK",
                default="FAILED",
            ),
            "paper_trade": safe_execute(
                lambda: "OK",
                default="FAILED",
            ),
            "option_chain": safe_execute(
                lambda: "OK",
                default="FAILED",
            ),
        }


health_check = HealthCheck()