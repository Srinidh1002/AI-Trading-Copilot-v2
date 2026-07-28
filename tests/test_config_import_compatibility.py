"""Compatibility contract for the root config.py / config package boundary."""


def test_config_exports_all_current_direct_import_names():
    from config import (
        ANGEL_API_KEY,
        ANGEL_CLIENT_ID,
        ANGEL_PIN,
        ANGEL_TOTP_SECRET,
        APP_NAME,
        BUILD,
        DEBUG_MODE,
        DEFAULT_SYMBOL,
        PHASE,
        REDIRECT_URI,
        UPSTOX_API_KEY,
        UPSTOX_API_SECRET,
        VERSION,
    )

    assert isinstance(DEBUG_MODE, bool)
    assert isinstance(DEFAULT_SYMBOL, str)
    assert all(
        isinstance(value, str)
        for value in (
            ANGEL_API_KEY,
            ANGEL_CLIENT_ID,
            ANGEL_PIN,
            ANGEL_TOTP_SECRET,
            UPSTOX_API_KEY,
            UPSTOX_API_SECRET,
            REDIRECT_URI,
            APP_NAME,
            VERSION,
            PHASE,
            BUILD,
        )
    )


def test_config_reexports_root_configuration_values_without_changes():
    import config

    root_config = __import__("sys").modules[
        "_ai_trading_copilot_root_config"
    ]
    package_version_fields = {
        "APP_NAME",
        "VERSION",
        "PHASE",
        "BUILD",
    }

    for name in dir(root_config):
        if name.isupper() and name not in package_version_fields:
            assert getattr(config, name) == getattr(root_config, name)
