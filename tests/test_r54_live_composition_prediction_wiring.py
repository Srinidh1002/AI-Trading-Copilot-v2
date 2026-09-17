from pathlib import Path


def test_live_compositions_build_and_pass_prediction_ledger():
    for relative in (
        "services/certification/"
        "task1c_parent_only_default_composition.py",
        "services/certification/"
        "task8_live_paper_default_composition.py",
    ):
        source = Path(relative).read_text(
            encoding="utf-8"
        )

        assert (
            "build_certified_prediction_ledger"
            in source
        )
        assert (
            "prediction_ledger=prediction_ledger"
            in source
        )


def test_authoritative_entry_point_owns_projection_and_save():
    source = Path(
        "services/paper_orchestration/"
        "authoritative_two_market_entry_point.py"
    ).read_text(encoding="utf-8")

    assert (
        "project_parent_decision_predictions"
        in source
    )
    assert "prediction_ledger.save_pair" in source
    assert "broker_order_submission" in source
