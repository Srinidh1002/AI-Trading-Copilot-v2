from datetime import datetime, timezone

import pytest

from services.dashboard_publication import DashboardPublicationEnvelopeV1
from services.dashboard_read_models.dashboard_option_intelligence_view_v1 import (
    DashboardOptionIntelligenceViewV1,
)
from services.dashboard_read_models.dashboard_runtime_operations_view_v1 import (
    DashboardRuntimeOperationsViewV1,
)


NOW = datetime(2026, 7, 30, 15, 0, tzinfo=timezone.utc)


def option_view():
    return DashboardOptionIntelligenceViewV1(
        source_id="option-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        status="READY",
        source_updated_at=NOW,
        pcr=1.1,
    )


def runtime_view():
    return DashboardRuntimeOperationsViewV1(
        source_id="cycle-1",
        runtime_status="COMPLETED",
        source_updated_at=NOW,
    )


def test_envelope_accepts_typed_wp4_views():
    value = DashboardPublicationEnvelopeV1(
        publication_id="publication-1",
        publication_sequence=1,
        published_at=NOW,
        source_updated_at=NOW,
        publication_status="NO_ACTION",
        freshness_status="FRESH",
        option_intelligence=option_view(),
        runtime_operations=runtime_view(),
    )

    assert value.option_intelligence.source_id == "option-1"
    assert value.runtime_operations.source_id == "cycle-1"


def test_envelope_serializes_wp4_views():
    value = DashboardPublicationEnvelopeV1(
        publication_id="publication-1",
        publication_sequence=1,
        published_at=NOW,
        source_updated_at=NOW,
        publication_status="NO_ACTION",
        freshness_status="FRESH",
        option_intelligence=option_view(),
        runtime_operations=runtime_view(),
    )

    raw = value.to_dict()
    assert raw["option_intelligence"]["source_id"] == "option-1"
    assert raw["runtime_operations"]["source_id"] == "cycle-1"


def test_envelope_rejects_untyped_wp4_views():
    with pytest.raises(TypeError, match="option_intelligence"):
        DashboardPublicationEnvelopeV1(
            publication_id="publication-1",
            publication_sequence=1,
            published_at=NOW,
            source_updated_at=NOW,
            publication_status="NO_ACTION",
            freshness_status="FRESH",
            option_intelligence=object(),
        )
