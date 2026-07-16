import json
from pathlib import Path


class LiveDashboardRepository:

    def save(
        self,
        dashboard,
    ):

        try:

            path = (
                Path("data")
                / "live_dashboard.json"
            )

            path.write_text(
                json.dumps(
                    dashboard,
                    indent=4,
                ),
                encoding="utf-8",
            )

            return path

        except Exception:

            return None