import json
from pathlib import Path


class PaperTradeMonitor:

    def save(
        self,
        trade,
    ):

        if not isinstance(
            trade,
            dict,
        ):
            return

        try:

            path = (
                Path("data")
                / "active_paper_trade.json"
            )

            path.write_text(
                json.dumps(
                    trade,
                    indent=4,
                ),
                encoding="utf-8",
            )

        except Exception:
            pass