from __future__ import annotations

from services.dashboard_read_models import (
    project_paper_trade_position_detail,
    project_three_target_trade_plan,
    project_trade_opportunity,
)

from .dashboard_publication_build_input_v1 import (
    DashboardPublicationBuildInputV1,
)
from .dashboard_publication_envelope_v1 import (
    DashboardPublicationEnvelopeV1,
)


class DashboardPublicationService:
    """Pure source-contract to immutable publication projection."""

    def build(
        self,
        value: DashboardPublicationBuildInputV1,
    ) -> DashboardPublicationEnvelopeV1:
        if type(value) is not DashboardPublicationBuildInputV1:
            raise TypeError(
                "value must be exact DashboardPublicationBuildInputV1"
            )

        opportunity = (
            project_trade_opportunity(value.trade_opportunity)
            if value.trade_opportunity is not None
            else None
        )
        trade_plan = (
            project_three_target_trade_plan(value.trade_plan)
            if value.trade_plan is not None
            else None
        )
        paper_position = (
            project_paper_trade_position_detail(value.p7_snapshot)
            if value.p7_snapshot is not None
            else None
        )

        return DashboardPublicationEnvelopeV1(
            publication_id=value.publication_id,
            publication_sequence=value.publication_sequence,
            published_at=value.published_at,
            source_updated_at=value.source_updated_at,
            publication_status=value.publication_status,
            freshness_status=value.freshness_status,
            cycle_result=value.cycle_result,
            opportunity=opportunity,
            trade_plan=trade_plan,
            paper_position=paper_position,
            blockers=value.blockers,
            warnings=value.warnings,
            errors=value.errors,
        )
