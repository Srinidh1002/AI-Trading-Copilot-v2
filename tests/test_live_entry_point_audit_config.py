"""
Tests for audit configuration at the live entry point.

Verifies that:
- DecisionAuditLogger can be instantiated without broker calls
- LiveOptionDecisionPipeline accepts configured audit parameters
- Configuration constants are properly defined

This test module does NOT execute the live trading script or broker calls.
"""

from services.decision_audit_logger import (
    DecisionAuditLogger,
)

from services.live_option_decision_pipeline import (
    LiveOptionDecisionPipeline,
)


def test_audit_logger_can_be_instantiated():
    """Verify DecisionAuditLogger can be created with default parameters."""

    logger = DecisionAuditLogger()

    assert logger is not None
    assert logger.file_path is not None
    assert str(logger.file_path).endswith(
        "decision_audit.jsonl"
    )


def test_pipeline_accepts_audit_logger_and_persist_flag():
    """Verify LiveOptionDecisionPipeline accepts audit configuration."""

    logger = DecisionAuditLogger()

    pipeline = LiveOptionDecisionPipeline(
        audit_logger=logger,
        persist_audit=True,
    )

    assert pipeline.audit_logger is logger
    assert pipeline.persist_audit is True


def test_pipeline_accepts_persist_audit_false():
    """Verify persistence can be disabled."""

    logger = DecisionAuditLogger()

    pipeline = LiveOptionDecisionPipeline(
        audit_logger=logger,
        persist_audit=False,
    )

    assert pipeline.audit_logger is logger
    assert pipeline.persist_audit is False


def test_pipeline_works_without_audit_logger():
    """Verify pipeline still works when audit logger is not provided."""

    pipeline = LiveOptionDecisionPipeline(
        audit_logger=None,
        persist_audit=False,
    )

    assert pipeline.audit_logger is None
    assert pipeline.persist_audit is False


def test_audit_logger_file_path_is_configurable():
    """Verify DecisionAuditLogger file path can be customized."""

    custom_path = "custom/audit/path.jsonl"

    logger = DecisionAuditLogger(
        file_path=custom_path
    )

    assert str(logger.file_path).endswith(
        "path.jsonl"
    )
