"""Offline MCX bias/provider-boundary checks.

No credentials.
No network.
No PAPER state.
"""

import ast
from pathlib import Path

from mcx.mcx_chain import (
    LEGACY_CHAIN_RETIRED,
    build_chain,
)


class FakeFYERSChain:
    provider = "FYERS"

    def build(
        self,
        product,
        window_steps=10,
    ):
        return {
            "status": "OK",
            "provider": "FYERS",
            "product": product,
            "window_steps": window_steps,
        }


def test_legacy_chain_is_retired():
    assert LEGACY_CHAIN_RETIRED is True


def test_legacy_chain_delegates_only_to_fyers_engine():
    result = build_chain(
        FakeFYERSChain(),
        "CRUDEOILM",
        window_steps=10,
    )

    assert result["status"] == "OK"
    assert result["provider"] == "FYERS"


def test_non_fyers_legacy_chain_fails_closed():
    result = build_chain(
        object(),
        "CRUDEOILM",
    )

    assert (
        result["status"]
        == "LEGACY_CHAIN_RETIRED"
    )


def test_bias_test_has_no_broker_login_authority():
    """Inspect Python structure, not raw self-referential text."""

    source = Path(
        "test_mcx_bias.py"
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    imported_modules = set()
    referenced_names = set()
    referenced_attributes = set()

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(
                    alias.name
                )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(
                    node.module
                )

        elif isinstance(node, ast.Name):
            referenced_names.add(
                node.id
            )

        elif isinstance(node, ast.Attribute):
            referenced_attributes.add(
                node.attr
            )

    # Structural provider-login checks.
    assert not any(
        module.lower().startswith(
            "smartapi"
        )
        for module in imported_modules
    )

    assert "pyotp" not in imported_modules

    assert "SmartConnect" not in referenced_names

    assert (
        "generateSession"
        not in referenced_attributes
    )

    assert "getenv" not in referenced_attributes
