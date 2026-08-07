from types import SimpleNamespace

import pytest

from services.certification.task8_live_paper_default_composition import (
    _validate_retained_task8_evaluations,
    build_task8_dependencies,
)


def _decision(*statuses):
    entries = tuple(
        SimpleNamespace(
            child=SimpleNamespace(
                observation_id=observation_id,
                terminal_status=status,
            )
        )
        for observation_id, status in statuses
    )
    return SimpleNamespace(entries=entries)


def test_default_factory_is_exposed_without_running_live_reads():
    assert callable(build_task8_dependencies)


def test_completed_children_require_exact_retained_evaluations():
    decision = _decision(
        ("nifty-observation", "COMPLETED"),
        ("sensex-observation", "COMPLETED"),
    )

    _validate_retained_task8_evaluations(
        decision,
        {
            "nifty-observation": object(),
            "sensex-observation": object(),
        },
    )


def test_failed_child_does_not_require_typed_evaluation():
    decision = _decision(
        ("nifty-observation", "COMPLETED"),
        ("sensex-observation", "FAILED"),
    )

    _validate_retained_task8_evaluations(
        decision,
        {
            "nifty-observation": object(),
        },
    )


def test_unavailable_child_does_not_require_typed_evaluation():
    decision = _decision(
        ("nifty-observation", "UNAVAILABLE"),
        ("sensex-observation", "COMPLETED"),
    )

    _validate_retained_task8_evaluations(
        decision,
        {
            "sensex-observation": object(),
        },
    )


def test_missing_completed_evaluation_fails_closed():
    decision = _decision(
        ("nifty-observation", "COMPLETED"),
        ("sensex-observation", "COMPLETED"),
    )

    with pytest.raises(
        RuntimeError,
        match="completed children",
    ):
        _validate_retained_task8_evaluations(
            decision,
            {
                "nifty-observation": object(),
            },
        )


def test_failed_child_must_not_have_unexpected_retained_evaluation():
    decision = _decision(
        ("nifty-observation", "COMPLETED"),
        ("sensex-observation", "FAILED"),
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected",
    ):
        _validate_retained_task8_evaluations(
            decision,
            {
                "nifty-observation": object(),
                "sensex-observation": object(),
            },
        )
