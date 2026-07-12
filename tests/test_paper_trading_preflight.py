from pathlib import Path

import pytest

import paper_trading_preflight as preflight


# ============================================================
# HELPERS
# ============================================================


def create_required_files(
    root,
):
    for relative_path in (
        preflight.REQUIRED_FILES
    ):
        path = (
            root
            / relative_path
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            "# test",
            encoding="utf-8",
        )


def complete_environment():
    return {
        "ANGEL_API_KEY": "secret",
        "ANGEL_CLIENT_CODE": "secret",
        "ANGEL_PIN": "secret",
        "ANGEL_TOTP_SECRET": "secret",
    }


# ============================================================
# CHECK OBJECT
# ============================================================


def test_make_check():

    result = (
        preflight.make_check(
            "Test",
            "PASS",
            "Success",
        )
    )

    assert result == {
        "name": "Test",
        "status": "PASS",
        "message": "Success",
    }


# ============================================================
# REQUIRED FILES
# ============================================================


def test_required_files_pass(
    tmp_path,
):
    create_required_files(
        tmp_path
    )

    checks = (
        preflight.check_required_files(
            tmp_path
        )
    )

    assert all(
        check[
            "status"
        ] == "PASS"
        for check in checks
    )


def test_missing_required_file_fails(
    tmp_path,
):
    checks = (
        preflight.check_required_files(
            tmp_path
        )
    )

    assert any(
        check[
            "status"
        ] == "FAIL"
        for check in checks
    )


def test_required_file_count(
    tmp_path,
):
    checks = (
        preflight.check_required_files(
            tmp_path
        )
    )

    assert len(
        checks
    ) == len(
        preflight.REQUIRED_FILES
    )


# ============================================================
# MODULE IMPORTS
# ============================================================


def test_required_modules_pass():

    imported = []

    def importer(
        name,
    ):
        imported.append(
            name
        )

        return object()

    checks = (
        preflight.check_required_modules(
            importer=importer
        )
    )

    assert all(
        check[
            "status"
        ] == "PASS"
        for check in checks
    )

    assert len(
        imported
    ) == len(
        preflight.REQUIRED_MODULES
    )


def test_module_import_failure():

    def importer(
        name,
    ):
        if name.endswith(
            "paper_trading_engine"
        ):
            raise ImportError(
                "missing"
            )

        return object()

    checks = (
        preflight.check_required_modules(
            importer=importer
        )
    )

    failures = [
        check
        for check in checks
        if check[
            "status"
        ] == "FAIL"
    ]

    assert len(
        failures
    ) == 1


# ============================================================
# CREDENTIALS
# ============================================================


def test_all_credentials_configured():

    checks = (
        preflight.check_angel_credentials(
            environment=(
                complete_environment()
            )
        )
    )

    assert all(
        check[
            "status"
        ] == "PASS"
        for check in checks
    )


def test_missing_credentials_fail():

    checks = (
        preflight.check_angel_credentials(
            environment={}
        )
    )

    assert all(
        check[
            "status"
        ] == "FAIL"
        for check in checks
    )


def test_empty_credentials_fail():

    environment = (
        complete_environment()
    )

    environment[
        "ANGEL_API_KEY"
    ] = "   "

    checks = (
        preflight.check_angel_credentials(
            environment=environment
        )
    )

    assert any(
        check[
            "name"
        ] == "Angel One API Key"
        and check[
            "status"
        ] == "FAIL"
        for check in checks
    )


def test_credential_values_not_exposed():

    secret = (
        "SUPER_SECRET_VALUE"
    )

    environment = (
        complete_environment()
    )

    environment[
        "ANGEL_API_KEY"
    ] = secret

    checks = (
        preflight.check_angel_credentials(
            environment=environment
        )
    )

    combined = str(
        checks
    )

    assert (
        secret
        not in combined
    )


def test_supported_alias_works():

    environment = (
        complete_environment()
    )

    del environment[
        "ANGEL_API_KEY"
    ]

    environment[
        "SMARTAPI_API_KEY"
    ] = "secret"

    checks = (
        preflight.check_angel_credentials(
            environment=environment
        )
    )

    api_check = next(
        check
        for check in checks
        if check[
            "name"
        ] == "Angel One API Key"
    )

    assert (
        api_check[
            "status"
        ]
        == "PASS"
    )


# ============================================================
# RUNTIME CONFIG
# ============================================================


def test_valid_runtime_config():

    checks = (
        preflight.check_runtime_configuration(
            config_loader=lambda: {
                "interval_seconds": 60.0,
                "timeout_seconds": 300.0,
            }
        )
    )

    assert all(
        check[
            "status"
        ] == "PASS"
        for check in checks
    )


def test_config_loader_failure():

    def loader():
        raise ValueError(
            "bad config"
        )

    checks = (
        preflight.check_runtime_configuration(
            config_loader=loader
        )
    )

    assert (
        checks[
            0
        ][
            "status"
        ]
        == "FAIL"
    )


@pytest.mark.parametrize(
    "interval",
    [
        0,
        -1,
        None,
        "60",
        True,
    ],
)
def test_invalid_runtime_interval(
    interval,
):

    checks = (
        preflight.check_runtime_configuration(
            config_loader=lambda: {
                "interval_seconds": interval,
                "timeout_seconds": 300.0,
            }
        )
    )

    assert (
        checks[
            0
        ][
            "status"
        ]
        == "FAIL"
    )


@pytest.mark.parametrize(
    "timeout",
    [
        0,
        -1,
        None,
        "300",
        True,
    ],
)
def test_invalid_runtime_timeout(
    timeout,
):

    checks = (
        preflight.check_runtime_configuration(
            config_loader=lambda: {
                "interval_seconds": 60.0,
                "timeout_seconds": timeout,
            }
        )
    )

    assert (
        checks[
            1
        ][
            "status"
        ]
        == "FAIL"
    )


# ============================================================
# PERSISTENCE
# ============================================================


def test_persistence_directory_passes(
    tmp_path,
):

    check = (
        preflight.check_persistence_directory(
            tmp_path
        )
    )

    assert (
        check[
            "status"
        ]
        == "PASS"
    )

    assert (
        tmp_path
        / "data"
    ).is_dir()


def test_persistence_probe_is_removed(
    tmp_path,
):

    preflight.check_persistence_directory(
        tmp_path
    )

    probe = (
        tmp_path
        / "data"
        / ".paper_trading_preflight_write_test"
    )

    assert (
        probe.exists()
        is False
    )


# ============================================================
# SAFETY
# ============================================================


def test_real_order_isolation_passes():

    check = (
        preflight.check_real_order_isolation()
    )

    assert (
        check[
            "status"
        ]
        == "PASS"
    )

    assert (
        "paper-trading"
        in check[
            "message"
        ].lower()
    )


# ============================================================
# OVERALL STATUS
# ============================================================


def test_overall_ready():

    checks = [
        preflight.make_check(
            "A",
            "PASS",
            "ok",
        ),
        preflight.make_check(
            "B",
            "PASS",
            "ok",
        ),
    ]

    assert (
        preflight.determine_overall_status(
            checks
        )
        == "READY"
    )


def test_overall_ready_with_warnings():

    checks = [
        preflight.make_check(
            "A",
            "PASS",
            "ok",
        ),
        preflight.make_check(
            "B",
            "WARN",
            "warning",
        ),
    ]

    assert (
        preflight.determine_overall_status(
            checks
        )
        == "READY_WITH_WARNINGS"
    )


def test_overall_not_ready():

    checks = [
        preflight.make_check(
            "A",
            "PASS",
            "ok",
        ),
        preflight.make_check(
            "B",
            "FAIL",
            "failed",
        ),
    ]

    assert (
        preflight.determine_overall_status(
            checks
        )
        == "NOT_READY"
    )


def test_failure_overrides_warning():

    checks = [
        preflight.make_check(
            "A",
            "WARN",
            "warning",
        ),
        preflight.make_check(
            "B",
            "FAIL",
            "failed",
        ),
    ]

    assert (
        preflight.determine_overall_status(
            checks
        )
        == "NOT_READY"
    )


# ============================================================
# REPORT
# ============================================================


def test_print_report(
    capsys,
):

    report = {
        "status": "READY",
        "checks": [
            preflight.make_check(
                "Test",
                "PASS",
                "Success",
            )
        ],
        "passed": 1,
        "warnings": 0,
        "failed": 0,
    }

    preflight.print_report(
        report
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "PAPER TRADING PREFLIGHT"
        in output
    )

    assert (
        "Status: READY"
        in output
    )

    assert (
        "NO REAL ORDER WAS PLACED"
        in output
    )


# ============================================================
# MAIN
# ============================================================


def test_main_returns_valid_exit_code():

    result = (
        preflight.main()
    )

    assert result in {
        0,
        1,
    }