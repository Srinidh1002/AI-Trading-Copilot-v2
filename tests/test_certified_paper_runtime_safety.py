from pathlib import Path

import pytest

from services.paper_orchestration.certified_runtime_safety import (
    CertifiedPaperRuntimeSafetyConfigV1,
    safety_banner,
    validate_repository_paper_safety,
    validate_required_angel_credentials,
    validate_runtime_paths,
)


def test_config_is_paper_only_and_observe_only_by_default():
    value = CertifiedPaperRuntimeSafetyConfigV1(
        instruments=("NIFTY",),
    )

    assert value.execution_mode == "PAPER"
    assert value.live_execution_eligible is False
    assert value.broker_order_submission is False
    assert value.new_entries_enabled is False
    assert value.monitoring_enabled is True


def test_entry_enabled_mode_still_never_enables_live_execution():
    value = CertifiedPaperRuntimeSafetyConfigV1(
        instruments=("NIFTY", "SENSEX"),
        observe_only=False,
    )

    assert value.new_entries_enabled is True
    assert value.live_execution_eligible is False
    assert value.broker_order_submission is False


@pytest.mark.parametrize(
    "instrument",
    ("BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "RELIANCE"),
)
def test_unsupported_instrument_is_rejected(instrument):
    with pytest.raises(ValueError, match="unsupported instruments"):
        CertifiedPaperRuntimeSafetyConfigV1(
            instruments=(instrument,),
        )


def test_live_mode_is_rejected():
    with pytest.raises(ValueError, match="execution_mode"):
        CertifiedPaperRuntimeSafetyConfigV1(
            instruments=("NIFTY",),
            execution_mode="LIVE",
        )

    with pytest.raises(ValueError, match="live execution"):
        CertifiedPaperRuntimeSafetyConfigV1(
            instruments=("NIFTY",),
            live_execution_eligible=True,
        )

    with pytest.raises(ValueError, match="broker order"):
        CertifiedPaperRuntimeSafetyConfigV1(
            instruments=("NIFTY",),
            broker_order_submission=True,
        )


def test_repository_configuration_must_be_paper_only():
    validate_repository_paper_safety(
        broker="PAPER",
        enable_paper_trading=True,
        enable_live_trading=False,
    )

    with pytest.raises(RuntimeError, match="BROKER"):
        validate_repository_paper_safety(
            broker="ANGEL",
            enable_paper_trading=True,
            enable_live_trading=False,
        )


def test_required_credentials_are_checked_without_returning_values():
    environment = {
        "ANGEL_API_KEY": "secret",
        "ANGEL_CLIENT_ID": "client",
        "ANGEL_PIN": "pin",
        "ANGEL_TOTP_SECRET": "totp",
    }
    assert validate_required_angel_credentials(environment) is None

    environment["ANGEL_PIN"] = ""
    with pytest.raises(RuntimeError, match="ANGEL_PIN"):
        validate_required_angel_credentials(environment)


def test_runtime_paths_are_created_and_writable(tmp_path):
    journal = tmp_path / "journal"
    logs = tmp_path / "logs"

    validate_runtime_paths(
        journal_directory=journal,
        log_directory=logs,
    )

    assert journal.is_dir()
    assert logs.is_dir()


def test_safety_banner_contains_no_secret_fields():
    value = CertifiedPaperRuntimeSafetyConfigV1(
        instruments=("NIFTY", "SENSEX"),
    )

    banner = safety_banner(value)

    assert banner["execution_mode"] == "PAPER"
    assert banner["broker_order_submission"] is False
    assert not any(
        token in key.upper()
        for key in banner
        for token in ("API_KEY", "PIN", "TOKEN", "SECRET", "PASSWORD")
    )
