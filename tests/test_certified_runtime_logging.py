import json
from datetime import datetime, timezone

from services.paper_orchestration.certified_runtime_logging import (
    CertifiedJsonLineLogger,
)


NOW = datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc)


def test_json_logger_writes_paper_safety_and_redacts_secrets(tmp_path):
    path = tmp_path / "runtime.jsonl"
    logger = CertifiedJsonLineLogger(file_path=path)

    logger.emit(
        event="runtime_starting",
        occurred_at=NOW,
        fields={
            "cycle_id": "cycle-1",
            "api_key": "secret-value",
            "nested": {"totp_secret": "secret-value"},
        },
    )
    logger.close()

    value = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert value["event"] == "RUNTIME_STARTING"
    assert value["execution_mode"] == "PAPER"
    assert value["live_execution_eligible"] is False
    assert value["api_key"] == "[REDACTED]"
    assert value["nested"]["totp_secret"] == "[REDACTED]"
