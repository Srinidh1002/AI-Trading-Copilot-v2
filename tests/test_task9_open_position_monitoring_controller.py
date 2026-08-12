import inspect

from services.certification.task9_live_paper_production_composition import (
    Task9LivePaperProductionRuntimeV1,
)
from services.certification.task9_open_position_monitoring_controller import (
    Task9OpenPositionMonitoringController,
)
from services.certification.task9_prediction_paper_trade_binding_store import (
    Task9PredictionPaperTradeBindingStore,
)
from services.certification.task9_certification_publication import (
    Task9CertificationPublicationAuthority,
)


def test_task9_open_monitoring_controller_has_injected_observation_and_cadence_seams():
    assert "observation_provider" in inspect.signature(
        Task9LivePaperProductionRuntimeV1.monitor_open_positions
    ).parameters
    assert {"iterations", "cadence_seconds", "sleep", "clock"} <= set(
        inspect.signature(Task9OpenPositionMonitoringController.run).parameters
    )
    assert callable(Task9PredictionPaperTradeBindingStore.list_all)
    assert callable(Task9CertificationPublicationAuthority.refresh)
