from datetime import datetime, timezone
from unittest.mock import patch

from services.paper_orchestration.certified_operator_controls import (
    CertifiedOperatorControls,
)
from services.paper_orchestration.certified_runtime_launcher import (
    CertifiedLauncherCompositionV1,
    CertifiedPaperRuntimeLauncher,
)
from services.paper_orchestration.certified_runtime_logging import (
    CertifiedJsonLineLogger,
)
from services.paper_orchestration.continuous_runtime_adapter import (
    ContinuousPaperOrchestrationRuntimeAdapter,
)


NOW = datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc)


def adapter():
    return object.__new__(ContinuousPaperOrchestrationRuntimeAdapter)


def test_launcher_requests_stop_and_logs_graceful_completion(tmp_path):
    runtime = adapter()
    logger = CertifiedJsonLineLogger(
        file_path=tmp_path / "runtime.jsonl"
    )
    composition = CertifiedLauncherCompositionV1(
        runtime_adapter=runtime,
        controls=CertifiedOperatorControls(observe_only=True),
        logger=logger,
    )

    with (
        patch.object(
            runtime,
            "run",
            return_value={"cycles_completed": 1},
        ),
        patch.object(runtime, "request_stop"),
    ):
        result = CertifiedPaperRuntimeLauncher(
            composition=composition,
            clock=lambda: NOW,
        ).run(max_cycles=1)

    assert result == {"cycles_completed": 1}
    text = (tmp_path / "runtime.jsonl").read_text(encoding="utf-8")
    assert "RUNTIME_STARTING" in text
    assert "RUNTIME_STOPPED" in text
    assert '"graceful_shutdown":true' in text


def test_launcher_requests_stop_on_failure(tmp_path):
    runtime = adapter()
    logger = CertifiedJsonLineLogger(
        file_path=tmp_path / "runtime.jsonl"
    )
    composition = CertifiedLauncherCompositionV1(
        runtime_adapter=runtime,
        controls=CertifiedOperatorControls(),
        logger=logger,
    )

    with (
        patch.object(
            runtime,
            "run",
            side_effect=RuntimeError("boom"),
        ),
        patch.object(runtime, "request_stop") as stop,
    ):
        try:
            CertifiedPaperRuntimeLauncher(
                composition=composition,
                clock=lambda: NOW,
            ).run(max_cycles=1)
        except RuntimeError:
            pass
        else:
            raise AssertionError("failure must propagate")

    stop.assert_called_once()
    text = (tmp_path / "runtime.jsonl").read_text(encoding="utf-8")
    assert "RUNTIME_FAILED" in text
