import argparse
from types import SimpleNamespace

import pytest

import services.certification.task9_production_startup_entrypoint as module


POLICIES = (
    "canonical_directional=directional.v1",
    "session=session.v1",
    "risk=risk.v1",
    "contract_selection=contract-selection.v1",
    "lifecycle=lifecycle.v1",
    "counting=counting.v1",
    "failure_disposition=failure-disposition.v1",
    "contract_spread=spread.v1",
    "liquidity=liquidity.v1",
    "minimum_risk_reward=rr.v1",
    "stop_target=stop-target.v1",
    "portfolio_concurrency=portfolio.v1",
)


def _argv():
    result = [
        "--automated-paper",
        "--runtime-config-id",
        "task9-runtime-20260818-a",
        "--runtime-config-version",
        "1",
        "--campaign-registry-location",
        "data/task9/campaign-registry.json",
        "--campaign-id",
        "task9-campaign-a",
        "--market-date",
        "2026-08-18",
        "--official-run-id",
        "task9-live-20260818-a",
        "--official-root",
        "data/task9/official",
        "--certification-registry-root",
        "data/task9/certification-registry",
        "--persistence-root",
        "data/task9",
        "--dashboard-publication-location",
        "data/task9/dashboard-publication.json",
        "--available-capital",
        "10000",
        "--risk-fraction",
        "0.02",
        "--maximum-quantity",
        "100",
        "--max-cycles",
        "1",
        "--cycle-interval-seconds",
        "0",
    ]

    for value in POLICIES:
        result.extend(
            [
                "--policy-reference",
                value,
            ]
        )

    return result


def test_cli_exposes_no_manual_preflight_or_live_execution_switch():
    parser = module._build_parser()

    destinations = {
        action.dest
        for action in parser._actions
    }

    forbidden = {
        "startup_preflight_id",
        "runtime_config_snapshot_id",
        "runtime_config_sha256",
        "approved",
        "launch_approved",
        "broker",
        "broker_order_submission",
        "live_execution_eligible",
        "enable_live_trading",
    }

    assert not (
        destinations
        & forbidden
    )


def test_cli_builds_paper_config_and_generates_internal_ids(
    monkeypatch,
):
    built = []
    runs = []

    runtime = SimpleNamespace(
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )

    def build_config(
        **kwargs,
    ):
        built.append(
            kwargs
        )
        return runtime

    monkeypatch.setattr(
        module,
        "build_task9_runtime_config",
        build_config,
    )

    monkeypatch.setattr(
        module,
        "_generated_startup_ids",
        lambda **_: (
            "generated-preflight",
            "generated-capture",
        ),
    )

    stats = SimpleNamespace(
        completed_cycles=1,
        graceful_shutdown=False,
    )

    bootstrap = SimpleNamespace(
        startup_preflight_id=(
            "generated-preflight"
        ),
    )

    def run_entrypoint(
        **kwargs,
    ):
        runs.append(
            kwargs
        )

        return SimpleNamespace(
            bootstrap=bootstrap,
            launcher_stats=stats,
        )

    monkeypatch.setattr(
        module,
        "run_task9_production_startup_entrypoint",
        run_entrypoint,
    )

    assert (
        module.main(
            _argv()
        )
        == 0
    )

    assert len(built) == 1

    assert (
        built[0]["execution_mode"]
        == "PAPER"
    )

    assert (
        built[0][
            "broker_order_submission"
        ]
        is False
    )

    assert (
        built[0][
            "live_execution_eligible"
        ]
        is False
    )

    assert len(runs) == 1

    assert (
        runs[0]["preflight_id"]
        == "generated-preflight"
    )

    assert (
        runs[0]["startup_capture_id"]
        == "generated-capture"
    )


def test_cli_returns_blocked_without_launcher_stats(
    monkeypatch,
):
    runtime = SimpleNamespace()

    monkeypatch.setattr(
        module,
        "build_task9_runtime_config",
        lambda **_: runtime,
    )

    monkeypatch.setattr(
        module,
        "_generated_startup_ids",
        lambda **_: (
            "generated-preflight",
            "generated-capture",
        ),
    )

    monkeypatch.setattr(
        module,
        "run_task9_production_startup_entrypoint",
        lambda **_: SimpleNamespace(
            bootstrap=SimpleNamespace(
                startup_preflight_id=(
                    "generated-preflight"
                ),
            ),
            launcher_stats=None,
        ),
    )

    assert (
        module.main(
            _argv()
        )
        == 2
    )


def test_policy_reference_conflicts_fail_closed():
    with pytest.raises(
        ValueError,
        match="conflicting policy reference",
    ):
        module._parse_policy_references(
            [
                "risk=a",
                "risk=b",
            ]
        )
