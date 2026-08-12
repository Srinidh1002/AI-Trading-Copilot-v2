from dataclasses import replace

import pytest

from services.certification.task9_paper_portfolio_policy_store import (
    Task9PaperPortfolioPolicyStore,
)
from tests.test_apt2_paper_lifecycle_certification import (
    _entry_input,
)


def test_policy_survives_restart_exactly(tmp_path):
    path = tmp_path / "portfolio-policies.json"

    original = _entry_input().portfolio_policy

    first = Task9PaperPortfolioPolicyStore(path)
    saved = first.save(original)

    assert saved == original

    restarted = Task9PaperPortfolioPolicyStore(path)
    recovered = restarted.recover(
        original.portfolio_policy_id
    )

    assert recovered == original
    assert recovered.to_dict() == original.to_dict()
    assert recovered.execution_mode == "PAPER"
    assert recovered.live_execution_eligible is False


def test_policy_save_is_idempotent(tmp_path):
    path = tmp_path / "portfolio-policies.json"
    policy = _entry_input().portfolio_policy

    store = Task9PaperPortfolioPolicyStore(path)

    first = store.save(policy)
    second = store.save(policy)

    assert first == policy
    assert second == policy

    restarted = Task9PaperPortfolioPolicyStore(path)

    assert (
        restarted.recover(
            policy.portfolio_policy_id
        )
        == policy
    )


def test_same_policy_id_with_different_payload_is_rejected(
    tmp_path,
):
    path = tmp_path / "portfolio-policies.json"
    policy = _entry_input().portfolio_policy

    store = Task9PaperPortfolioPolicyStore(path)

    store.save(policy)

    conflicting = replace(
        policy,
        maximum_concurrent_trades=(
            policy.maximum_concurrent_trades + 1
        ),
    )

    with pytest.raises(
        ValueError,
        match="portfolio policy identity conflict",
    ):
        store.save(conflicting)


def test_unknown_policy_returns_none(tmp_path):
    store = Task9PaperPortfolioPolicyStore(
        tmp_path / "portfolio-policies.json"
    )

    assert store.recover("missing-policy") is None