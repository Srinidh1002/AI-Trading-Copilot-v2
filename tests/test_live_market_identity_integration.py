from pathlib import Path


LIVE_ENTRY_POINT = Path(
    "live_option_decision_nifty.py"
)


def _runner_content():
    return LIVE_ENTRY_POINT.read_text(
        encoding="utf-8"
    )


def test_live_runner_imports_market_identity_guard():
    content = _runner_content()

    assert (
        "from services.market_identity_guard import ("
        in content
    )

    assert (
        "validate_market_identity,"
        in content
    )


def test_live_runner_validates_market_identity():
    content = _runner_content()

    expected = """MARKET_IDENTITY_VALIDATION = (
    validate_market_identity(
        UNDERLYING_CONFIGURATION,
        MARKET_SESSION_CONFIGURATION,
    )
)"""

    assert (
        expected
        in content
    )


def test_market_identity_validation_occurs_after_session_configuration():
    content = _runner_content()

    session_position = content.index(
        "MARKET_SESSION_CONFIGURATION = ("
    )

    validation_position = content.index(
        "MARKET_IDENTITY_VALIDATION = ("
    )

    assert (
        session_position
        < validation_position
    )


def test_market_identity_validation_occurs_before_market_session_precheck():
    content = _runner_content()

    validation_position = content.index(
        "MARKET_IDENTITY_VALIDATION = ("
    )

    precheck_position = content.index(
        "pre_session = None"
    )

    assert (
        validation_position
        < precheck_position
    )


def test_market_identity_validation_occurs_before_live_spot_fetch():
    content = _runner_content()

    validation_position = content.index(
        "MARKET_IDENTITY_VALIDATION = ("
    )

    spot_fetch_position = content.index(
        "Fetching live"
    )

    assert (
        validation_position
        < spot_fetch_position
    )


def test_market_identity_validation_uses_canonical_configurations():
    content = _runner_content()

    expected = """        UNDERLYING_CONFIGURATION,
        MARKET_SESSION_CONFIGURATION,"""

    assert (
        expected
        in content
    )


def test_live_runner_does_not_construct_identity_guard_from_market_literals():
    content = _runner_content()

    validation_start = content.index(
        "MARKET_IDENTITY_VALIDATION = ("
    )

    header_position = content.index(
        "# HEADER",
        validation_start,
    )

    validation_block = content[
        validation_start:
        header_position
    ]

    forbidden_literals = (
        '"NIFTY"',
        '"SENSEX"',
        '"NSE"',
        '"BSE"',
        '"NFO"',
        '"BFO"',
    )

    for literal in forbidden_literals:
        assert (
            literal
            not in validation_block
        )
