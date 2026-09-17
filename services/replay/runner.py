"""Deterministic acceptance checks for canonical offline replays."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import Mapping

from services.canonical.pipeline import (
    CanonicalPipelineDependencies,
    run_canonical_pipeline,
)
from services.contracts.final_decision_v1 import FinalDecisionV1
from services.contracts.market_snapshot_v1 import MarketSnapshotV1
from services.contracts.replay_fixture_v1 import (
    ReplayExpectationsV1,
    ReplayFixtureV1,
)

from .loader import load_replay_fixture
from .models import (
    ReplayAcceptanceResultV1,
    ReplayExpectationMismatchV1,
    ReplaySuiteResultV1,
)
from services.observability import AuditContext, AuditEmitter, create_audit_event


def run_replay_file(
    path: str | Path,
    *,
    dependencies: CanonicalPipelineDependencies | None = None,
    pipeline_runner: Callable[[MarketSnapshotV1], FinalDecisionV1] | None = None,
    audit_emitter: AuditEmitter | None = None,
    audit_context: AuditContext | None = None,
) -> ReplayAcceptanceResultV1:
    """Load and run one offline replay fixture."""
    fixture = load_replay_fixture(path)

    return run_replay_fixture(
        fixture,
        dependencies=dependencies,
        pipeline_runner=pipeline_runner,
        audit_emitter=audit_emitter, audit_context=audit_context,
    )

def run_replay_fixture(
    fixture: ReplayFixtureV1,
    *,
    dependencies: CanonicalPipelineDependencies | None = None,
    pipeline_runner: Callable[[MarketSnapshotV1], FinalDecisionV1] | None = None,
    audit_emitter: AuditEmitter | None = None,
    audit_context: AuditContext | None = None,
) -> ReplayAcceptanceResultV1:
    """Run one saved snapshot through the canonical pipeline and evaluate it.

    The fixture is the sole market input. This function does not prepare trades,
    persist state, or invoke provider or broker APIs.
    """
    emitter = audit_emitter or AuditEmitter()
    emitter.emit(create_audit_event("REPLAY_STARTED", component="replay", operation="fixture", outcome="STARTED", context=audit_context, fixture_id=fixture.fixture_id, snapshot_id=fixture.snapshot.snapshot_id, symbol=fixture.snapshot.symbol))
    try:
        if pipeline_runner is None:
            decision = run_canonical_pipeline(fixture.snapshot, dependencies=dependencies, audit_emitter=emitter, audit_context=audit_context)
        else:
            decision = pipeline_runner(fixture.snapshot)
    except Exception:
        emitter.emit(create_audit_event("REPLAY_FAILED", component="replay", operation="fixture", outcome="FAILED", severity="ERROR", context=audit_context, fixture_id=fixture.fixture_id, snapshot_id=fixture.snapshot.snapshot_id, errors=("Replay pipeline failed.",)))
        raise
    if not isinstance(decision, FinalDecisionV1):
        raise TypeError("pipeline_runner must return FinalDecisionV1.")
    result = evaluate_replay_expectations(fixture, decision)
    emitter.emit(create_audit_event("REPLAY_COMPLETED", component="replay", operation="fixture", outcome="SUCCEEDED" if result.passed else "FAILED", severity="INFO" if result.passed else "WARNING", context=audit_context, fixture_id=fixture.fixture_id, snapshot_id=fixture.snapshot.snapshot_id, decision_id=decision.decision_id, symbol=decision.symbol, attributes={"replay_status": result.status, "error_count": len(result.mismatches)}))
    return result


def evaluate_replay_expectations(
    fixture: ReplayFixtureV1,
    decision: FinalDecisionV1,
) -> ReplayAcceptanceResultV1:
    """Compare explicit expectations using stable, deterministic decision fields."""
    expectations = fixture.expectations
    actual = {
        "action": decision.action,
        "authorization_status": decision.authorization_status,
        "execution_status": decision.execution_status,
        "direction": decision.direction,
        "validation_passed": decision.validation_passed,
        "data_health_status": decision.data_health.overall_status,
        "blocking_reasons": tuple(decision.blocking_reasons),
        "internal_errors": tuple(decision.internal_errors),
        "market_regime": decision.market_regime,
        "trend_strength": decision.trend_strength,
        "volatility_state": decision.volatility_state,
        "option_type": decision.option_type,
        "trade_plan_present": decision.trade_plan is not None,
        "missing_sources": tuple(decision.data_health.missing_sources),
        "stale_sources": tuple(decision.data_health.stale_sources),
        "confidence": decision.confidence,
        "technical_score": decision.technical_score,
        "options_score": decision.options_score,
        "institutional_score": decision.institutional_score,
    }
    mismatches: list[ReplayExpectationMismatchV1] = []
    insufficient = False
    for field, expected, actual_name, comparison in _checks(expectations):
        actual_value = actual[actual_name]
        if actual_value is None:
            mismatches.append(ReplayExpectationMismatchV1(field, expected, actual_value))
            insufficient = True
        elif not comparison(expected, actual_value):
            mismatches.append(ReplayExpectationMismatchV1(field, expected, actual_value))
    mismatches.sort(key=lambda mismatch: mismatch.field)
    status = "INSUFFICIENT_DATA" if insufficient else "FAIL" if mismatches else "PASS"
    return ReplayAcceptanceResultV1(
        fixture_id=fixture.fixture_id,
        fixture_name=fixture.name,
        passed=status == "PASS",
        decision=decision,
        mismatches=tuple(mismatches),
        status=status,
    )


def run_replay_directory(
    path: str | Path,
    *,
    pattern: str = "*.json",
    dependencies_by_fixture: Mapping[str, CanonicalPipelineDependencies | None] | None = None,
    pipeline_runner_by_fixture: Mapping[
        str, Callable[[MarketSnapshotV1], FinalDecisionV1]
    ] | None = None,
    audit_emitter: AuditEmitter | None = None,
    audit_context: AuditContext | None = None,
) -> ReplaySuiteResultV1:
    """Run matching JSON fixtures in filename order without stopping on errors."""
    emitter = audit_emitter or AuditEmitter()
    directory = Path(path)
    display_directory = directory.name or "."
    if not directory.exists() or not directory.is_dir():
        detail = "Replay path must be an existing directory."
        return _suite(display_directory, (_error_result(display_directory, detail),), (detail,))

    emitter.emit(create_audit_event("REPLAY_SUITE_STARTED", component="replay", operation="directory", outcome="STARTED", context=audit_context, attributes={"fixture_name": display_directory}))

    dependencies_by_fixture = dependencies_by_fixture or {}
    pipeline_runner_by_fixture = pipeline_runner_by_fixture or {}
    paths = sorted(directory.glob(pattern), key=lambda item: item.name.casefold())
    results: list[ReplayAcceptanceResultV1] = []
    errors: list[str] = []
    for fixture_path in paths:
        if not fixture_path.is_file() or fixture_path.suffix.casefold() != ".json":
            continue
        fallback = fixture_path.name
        try:
            fixture = load_replay_fixture(fixture_path)
            dependency = dependencies_by_fixture.get(fixture.fixture_id)
            runner = pipeline_runner_by_fixture.get(fixture.fixture_id)
            # A normalized filename is a documented fallback for dependency maps.
            dependency = dependency if fixture.fixture_id in dependencies_by_fixture else dependencies_by_fixture.get(fallback)
            runner = runner if fixture.fixture_id in pipeline_runner_by_fixture else pipeline_runner_by_fixture.get(fallback)
            results.append(run_replay_fixture(fixture, dependencies=dependency, pipeline_runner=runner, audit_emitter=emitter, audit_context=audit_context))
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            errors.append(f"{fallback}: {detail}")
            results.append(_error_result(fallback, detail))
            emitter.emit(create_audit_event("REPLAY_FIXTURE_ERROR", component="replay", operation="directory", outcome="FAILED", severity="ERROR", context=audit_context, fixture_id=f"file:{fallback}", errors=(type(exc).__name__,)))
    warning = ("No matching replay fixtures were found.",) if not results else ()
    suite = _suite(display_directory, tuple(results), tuple(errors), warning)
    emitter.emit(create_audit_event("REPLAY_SUITE_COMPLETED", component="replay", operation="directory", outcome="SUCCEEDED", context=audit_context, suite_id=suite.suite_id, attributes={"suite_total": suite.total, "suite_passed": suite.passed, "suite_failed": suite.failed}))
    return suite


def _checks(expectations: ReplayExpectationsV1):
    aliases = {
        "action": ("action", "action"), "direction": ("direction", "direction"),
        "authorization_status": ("authorization_status", "authorization_status"),
        "execution_status": ("execution_status", "execution_status"),
        "data_health_status": ("data_health_status", "data_health_status"),
        "validation_passed": ("validation_passed", "validation_passed"),
        "blocking_reasons": ("blocking_reasons", "blocking_reasons"),
        "internal_errors": ("internal_errors", "internal_errors"),
        "expected_action": ("expected_action", "action"),
        "expected_direction": ("expected_direction", "direction"),
        "expected_authorization": ("expected_authorization", "authorization_status"),
        "expected_execution_status": ("expected_execution_status", "execution_status"),
        "expected_data_health_status": ("expected_data_health_status", "data_health_status"),
        "expected_validation_passed": ("expected_validation_passed", "validation_passed"),
        "expected_market_regime": ("expected_market_regime", "market_regime"),
        "expected_trend_strength": ("expected_trend_strength", "trend_strength"),
        "expected_volatility_state": ("expected_volatility_state", "volatility_state"),
        "expected_option_type": ("expected_option_type", "option_type"),
        "expected_trade_plan_present": ("expected_trade_plan_present", "trade_plan_present"),
        "expected_blockers": ("expected_blockers", "blocking_reasons"),
        "expected_missing_sources": ("expected_missing_sources", "missing_sources"),
        "expected_stale_sources": ("expected_stale_sources", "stale_sources"),
    }
    for attribute, (field, actual_name) in aliases.items():
        expected = getattr(expectations, attribute)
        if expected is not None:
            comparator = _contains_all if isinstance(expected, tuple) else _equal
            yield field, expected, actual_name, comparator
    for field, actual_name, bound in (
        ("confidence_min", "confidence", "min"), ("confidence_max", "confidence", "max"),
        ("technical_score_min", "technical_score", "min"), ("technical_score_max", "technical_score", "max"),
        ("options_score_min", "options_score", "min"), ("options_score_max", "options_score", "max"),
        ("institutional_score_min", "institutional_score", "min"), ("institutional_score_max", "institutional_score", "max"),
    ):
        expected = getattr(expectations, field)
        if expected is not None:
            yield field, expected, actual_name, (lambda value, actual: actual >= value) if bound == "min" else (lambda value, actual: actual <= value)


def _equal(expected: object, actual: object) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        return _normalise_text(expected) == _normalise_text(actual)
    return expected == actual


def _contains_all(expected: object, actual: object) -> bool:
    if not isinstance(expected, tuple) or not isinstance(actual, tuple):
        return False
    actual_values = {_normalise_text(str(value)) for value in actual}
    return all(_normalise_text(value) in actual_values for value in expected)


def _normalise_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _error_result(fixture_name: str, detail: str) -> ReplayAcceptanceResultV1:
    return ReplayAcceptanceResultV1(
        fixture_id=f"file:{fixture_name}", fixture_name=fixture_name, passed=False,
        decision=None, status="ERROR", error_detail=detail,
    )


def _suite(
    directory: str,
    results: tuple[ReplayAcceptanceResultV1, ...],
    errors: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> ReplaySuiteResultV1:
    suite_id = "replay-suite-" + sha256(
        (directory + "|" + "|".join(result.fixture_id for result in results)).encode("utf-8")
    ).hexdigest()[:16]
    return ReplaySuiteResultV1(
        suite_id=suite_id, directory=directory, results=results,
        warnings=warnings, errors_detail=errors,
    )
