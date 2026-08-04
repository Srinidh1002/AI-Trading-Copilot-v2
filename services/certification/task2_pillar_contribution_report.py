"""Offline deterministic projection used to certify Task 2A provenance closure."""
from __future__ import annotations

import json
from dataclasses import dataclass

from services.contracts.market_analysis_pillar_contribution_v1 import MarketAnalysisPillarContributionCollectionV1


@dataclass(frozen=True, slots=True)
class Task2PillarContributionReportV1:
    contributions: MarketAnalysisPillarContributionCollectionV1
    schema_version: str = "task2_pillar_contribution_report.v1"

    def __post_init__(self) -> None:
        if type(self.contributions) is not MarketAnalysisPillarContributionCollectionV1 or self.schema_version != "task2_pillar_contribution_report.v1":
            raise TypeError("typed Task 2 contribution report")

    def to_dict(self) -> dict[str, object]:
        data = self.contributions.to_dict()
        return {"schema_version": self.schema_version, "market": {key: data[key] for key in ("underlying_symbol", "exchange", "cycle_id", "observation_id", "evaluated_at", "contribution_count")}, "ordered_pillar_names": [item["pillar_name"] for item in data["contributions"]], "contributions": data["contributions"]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)


def build_task2_pillar_contribution_report(collection: MarketAnalysisPillarContributionCollectionV1) -> Task2PillarContributionReportV1:
    return Task2PillarContributionReportV1(collection)
