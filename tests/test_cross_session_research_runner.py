"""
Tests for CrossSessionResearchRunner.
"""

from copy import deepcopy

import pytest

from services.cross_session_research_runner import (
    CrossSessionResearchRunner,
)


class FakeArchive:
    def __init__(
        self,
        result,
    ):
        self.result = result
        self.calls = []

    def load_reports(
        self,
        *,
        start_date=None,
        end_date=None,
    ):
        self.calls.append(
            {
                "start_date": start_date,
                "end_date": end_date,
            }
        )

        return deepcopy(
            self.result
        )


class FakeIntelligence:
    def __init__(
        self,
        result,
    ):
        self.result = result
        self.calls = []

    def analyze(
        self,
        reports,
    ):
        self.calls.append(
            deepcopy(
                reports
            )
        )

        return deepcopy(
            self.result
        )


def build_archive_result(
    *,
    status="COMPLETED",
    start_date="2026-07-01",
    end_date="2026-07-05",
    reports=None,
    errors=None,
):
    if reports is None:
        reports = []

    if errors is None:
        errors = []

    return {
        "status": status,
        "read_only": True,
        "start_date": start_date,
        "end_date": end_date,
        "count": len(
            reports
        ),
        "reports": deepcopy(
            reports
        ),
        "errors": deepcopy(
            errors
        ),
    }


def build_intelligence_result(
    *,
    status="COMPLETED",
    sessions_observed=0,
):
    return {
        "status": status,
        "read_only": True,
        "research_only": True,
        "sessions_observed": (
            sessions_observed
        ),
        "session_dates": [],
        "research_observations": [],
    }


_UNSET = object()


def build_runner(
    *,
    archive_result=_UNSET,
    intelligence_result=_UNSET,
):
    if archive_result is _UNSET:
        archive_result = (
            build_archive_result()
        )

    if intelligence_result is _UNSET:
        intelligence_result = (
            build_intelligence_result()
        )

    archive = FakeArchive(
        archive_result
    )

    intelligence = FakeIntelligence(
        intelligence_result
    )

    runner = CrossSessionResearchRunner(
        archive=archive,
        intelligence=intelligence,
    )

    return (
        runner,
        archive,
        intelligence,
    )


def test_run_returns_completed_status():
    runner, _, _ = build_runner()

    result = runner.run()

    assert result["status"] == "COMPLETED"


def test_run_is_read_only():
    runner, _, _ = build_runner()

    result = runner.run()

    assert result["read_only"] is True


def test_run_is_research_only():
    runner, _, _ = build_runner()

    result = runner.run()

    assert result["research_only"] is True


def test_date_range_is_forwarded_to_archive():
    runner, archive, _ = build_runner()

    runner.run(
        start_date="2026-07-10",
        end_date="2026-07-20",
    )

    assert archive.calls == [
        {
            "start_date": "2026-07-10",
            "end_date": "2026-07-20",
        }
    ]


def test_archive_dates_are_preserved():
    archive_result = build_archive_result(
        start_date="2026-06-01",
        end_date="2026-06-30",
    )

    runner, _, _ = build_runner(
        archive_result=archive_result,
    )

    result = runner.run(
        start_date="2026-01-01",
        end_date="2026-12-31",
    )

    assert (
        result["start_date"]
        == "2026-06-01"
    )

    assert (
        result["end_date"]
        == "2026-06-30"
    )


def test_requested_dates_are_fallback_when_archive_omits_dates():
    archive_result = {
        "status": "COMPLETED",
        "reports": [],
        "errors": [],
    }

    runner, _, _ = build_runner(
        archive_result=archive_result,
    )

    result = runner.run(
        start_date="2026-07-01",
        end_date="2026-07-31",
    )

    assert (
        result["start_date"]
        == "2026-07-01"
    )

    assert (
        result["end_date"]
        == "2026-07-31"
    )


def test_reports_are_forwarded_to_intelligence():
    reports = [
        {
            "session_date": "2026-07-01",
        },
        {
            "session_date": "2026-07-02",
        },
    ]

    archive_result = build_archive_result(
        reports=reports,
    )

    runner, _, intelligence = build_runner(
        archive_result=archive_result,
    )

    runner.run()

    assert intelligence.calls == [
        reports
    ]


def test_reports_loaded_matches_actual_report_list():
    reports = [
        {
            "session_date": "2026-07-01",
        },
        {
            "session_date": "2026-07-02",
        },
        {
            "session_date": "2026-07-03",
        },
    ]

    archive_result = build_archive_result(
        reports=reports,
    )

    archive_result["count"] = 999

    runner, _, _ = build_runner(
        archive_result=archive_result,
    )

    result = runner.run()

    assert result["reports_loaded"] == 3


def test_archive_result_input_is_not_modified():
    archive_result = build_archive_result(
        reports=[
            {
                "session_date": "2026-07-01",
                "nested": {
                    "value": 10,
                },
            }
        ],
    )

    original = deepcopy(
        archive_result
    )

    runner, _, _ = build_runner(
        archive_result=archive_result,
    )

    runner.run()

    assert archive_result == original


def test_intelligence_cannot_mutate_archive_reports():
    reports = [
        {
            "session_date": "2026-07-01",
            "nested": {
                "value": 10,
            },
        }
    ]

    archive_result = build_archive_result(
        reports=reports,
    )

    class MutatingIntelligence:
        def analyze(
            self,
            received_reports,
        ):
            received_reports[
                0
            ][
                "nested"
            ][
                "value"
            ] = 999

            return (
                build_intelligence_result(
                    sessions_observed=1,
                )
            )

    archive = FakeArchive(
        archive_result
    )

    runner = CrossSessionResearchRunner(
        archive=archive,
        intelligence=(
            MutatingIntelligence()
        ),
    )

    runner.run()

    assert (
        archive.result[
            "reports"
        ][
            0
        ][
            "nested"
        ][
            "value"
        ]
        == 10
    )


def test_intelligence_result_is_preserved():
    intelligence_result = (
        build_intelligence_result(
            sessions_observed=5,
        )
    )

    intelligence_result[
        "research_observations"
    ] = [
        "Observation A",
        "Observation B",
    ]

    runner, _, _ = build_runner(
        intelligence_result=(
            intelligence_result
        ),
    )

    result = runner.run()

    assert (
        result["intelligence"]
        == intelligence_result
    )


def test_result_is_independent_from_intelligence_result():
    intelligence_result = (
        build_intelligence_result(
            sessions_observed=1,
        )
    )

    runner, _, _ = build_runner(
        intelligence_result=(
            intelligence_result
        ),
    )

    result = runner.run()

    intelligence_result[
        "sessions_observed"
    ] = 999

    assert (
        result[
            "intelligence"
        ][
            "sessions_observed"
        ]
        == 1
    )


def test_archive_errors_are_preserved():
    archive_result = build_archive_result(
        errors=[
            {
                "session_date": "2026-07-02",
                "error": "Invalid JSON",
            }
        ],
    )

    runner, _, _ = build_runner(
        archive_result=archive_result,
    )

    result = runner.run()

    assert result["archive_errors"] == [
        {
            "session_date": "2026-07-02",
            "error": "Invalid JSON",
        }
    ]


def test_archive_errors_create_component_errors():
    archive_result = build_archive_result(
        errors=[
            {
                "session_date": "2026-07-02",
                "error": "Invalid JSON",
            }
        ],
    )

    runner, _, _ = build_runner(
        archive_result=archive_result,
    )

    result = runner.run()

    assert result["component_errors"] == [
        {
            "component": (
                "research_report_archive"
            ),
            "error": {
                "session_date": "2026-07-02",
                "error": "Invalid JSON",
            },
        }
    ]


def test_archive_errors_produce_completed_with_errors():
    archive_result = build_archive_result(
        errors=[
            {
                "error": "Broken archive",
            }
        ],
    )

    runner, _, _ = build_runner(
        archive_result=archive_result,
    )

    result = runner.run()

    assert (
        result["status"]
        == "COMPLETED_WITH_ERRORS"
    )


@pytest.mark.parametrize(
    "archive_status",
    [
        "FAILED",
        "ERROR",
    ],
)
def test_failed_archive_status_fails_runner(
    archive_status,
):
    archive_result = build_archive_result(
        status=archive_status,
    )

    runner, _, _ = build_runner(
        archive_result=archive_result,
    )

    result = runner.run()

    assert result["status"] == "FAILED"


@pytest.mark.parametrize(
    "intelligence_status",
    [
        "FAILED",
        "ERROR",
    ],
)
def test_failed_intelligence_status_fails_runner(
    intelligence_status,
):
    intelligence_result = (
        build_intelligence_result(
            status=intelligence_status,
        )
    )

    runner, _, _ = build_runner(
        intelligence_result=(
            intelligence_result
        ),
    )

    result = runner.run()

    assert result["status"] == "FAILED"


@pytest.mark.parametrize(
    "archive_result",
    [
        None,
        [],
        "invalid",
        123,
        True,
    ],
)
def test_invalid_archive_results_are_normalized(
    archive_result,
):
    archive = FakeArchive(
        archive_result
    )

    intelligence = FakeIntelligence(
        build_intelligence_result()
    )

    runner = CrossSessionResearchRunner(
        archive=archive,
        intelligence=intelligence,
    )

    result = runner.run()

    assert result["reports_loaded"] == 0
    assert result["archive_errors"] == []
    assert intelligence.calls == [
        []
    ]


@pytest.mark.parametrize(
    "reports",
    [
        None,
        {},
        "invalid",
        123,
        True,
        (),
    ],
)
def test_invalid_reports_are_normalized(
    reports,
):
    archive_result = {
        "status": "COMPLETED",
        "reports": reports,
        "errors": [],
    }

    runner, _, intelligence = build_runner(
        archive_result=archive_result,
    )

    result = runner.run()

    assert result["reports_loaded"] == 0
    assert intelligence.calls == [
        []
    ]


@pytest.mark.parametrize(
    "archive_errors",
    [
        None,
        {},
        "invalid",
        123,
        True,
        (),
    ],
)
def test_invalid_archive_errors_are_normalized(
    archive_errors,
):
    archive_result = {
        "status": "COMPLETED",
        "reports": [],
        "errors": archive_errors,
    }

    runner, _, _ = build_runner(
        archive_result=archive_result,
    )

    result = runner.run()

    assert result["archive_errors"] == []
    assert result["component_errors"] == []


@pytest.mark.parametrize(
    "intelligence_result",
    [
        None,
        [],
        "invalid",
        123,
        True,
    ],
)
def test_invalid_intelligence_results_are_normalized(
    intelligence_result,
):
    runner, _, _ = build_runner(
        intelligence_result=(
            intelligence_result
        ),
    )

    result = runner.run()

    assert result["intelligence"] == {}

    assert (
        result["status"]
        == "COMPLETED_WITH_ERRORS"
    )


def test_empty_intelligence_status_is_completed_with_errors():
    runner, _, _ = build_runner(
        intelligence_result={},
    )

    result = runner.run()

    assert (
        result["status"]
        == "COMPLETED_WITH_ERRORS"
    )


def test_archive_status_is_exposed():
    archive_result = build_archive_result(
        status="PARTIAL",
    )

    runner, _, _ = build_runner(
        archive_result=archive_result,
    )

    result = runner.run()

    assert (
        result["archive_status"]
        == "PARTIAL"
    )


def test_no_execution_authority_fields_are_added():
    runner, _, _ = build_runner()

    result = runner.run()

    forbidden_fields = {
        "place_order",
        "execute_order",
        "broker",
        "order_id",
        "quantity",
        "entry_price",
        "stop_loss",
        "target",
        "trade_authorized",
    }

    assert forbidden_fields.isdisjoint(
        result.keys()
    )


def test_runner_can_process_empty_archive():
    runner, _, _ = build_runner(
        archive_result=(
            build_archive_result(
                reports=[],
            )
        ),
        intelligence_result=(
            build_intelligence_result(
                sessions_observed=0,
            )
        ),
    )

    result = runner.run()

    assert result["status"] == "COMPLETED"
    assert result["reports_loaded"] == 0

    assert (
        result[
            "intelligence"
        ][
            "sessions_observed"
        ]
        == 0
    )