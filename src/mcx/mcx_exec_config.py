"""Provider-scoped MCX execution calibration authority.

Certification calibration is specific to provider + product + real live
market-depth evidence.

Legacy unscoped calibration may remain on disk for audit/history, but cannot
authorize FYERS certification.
"""

from __future__ import annotations

import json
import os


CONFIG_PATH = (
    "data/execution_evidence/mcx/"
    "exec_config.json"
)

CONFIG_SCHEMA_VERSION = 2

CANONICAL_EXECUTION_PROVIDER = "FYERS"

SUPPORTED_PRODUCTS = (
    "CRUDEOILM",
    "GOLDM",
    "NATGASMINI",
)

CALIBRATION_EVIDENCE_KIND = (
    "LIVE_MARKET_DEPTH"
)


PRODUCT_EXEC_CONFIG = {
    product: {
        "calibration_provider":
            CANONICAL_EXECUTION_PROVIDER,
        "depth_quantity_semantics_verified":
            False,
        "depth_quantity_unit":
            None,
        "execution_freshness_calibrated":
            False,
        "execution_quote_max_age_seconds":
            None,
        "calibrated_at":
            None,
        "evidence_ref":
            None,
        "evidence_kind":
            None,
    }
    for product in SUPPORTED_PRODUCTS
}


def _text(value):
    return str(
        value or ""
    ).strip()


def _product(value):
    return _text(
        value
    ).upper()


def _provider(value):
    return _text(
        value
    ).upper()


def load_config():
    """Read only. Never upgrades/writes the evidence file."""

    if not os.path.exists(
        CONFIG_PATH
    ):
        return {}

    try:
        with open(
            CONFIG_PATH,
            encoding="utf-8",
        ) as handle:
            raw = json.load(
                handle
            )

        return (
            raw
            if isinstance(
                raw,
                dict,
            )
            else {}
        )

    except Exception:
        return {}


def _default_status(
    product,
    provider,
    reason,
):
    return {
        "product": product,
        "calibration_provider":
            provider,
        "provider_scoped":
            False,
        "calibration_valid":
            False,
        "depth_quantity_semantics_verified":
            False,
        "depth_quantity_unit":
            None,
        "execution_freshness_calibrated":
            False,
        "execution_quote_max_age_seconds":
            None,
        "calibrated_at":
            None,
        "evidence_ref":
            None,
        "evidence_kind":
            None,
        "reason": reason,
    }


def get_provider_product_config(
    product,
    provider=CANONICAL_EXECUTION_PROVIDER,
):
    product = _product(
        product
    )

    provider = _provider(
        provider
    )

    if (
        product
        not in SUPPORTED_PRODUCTS
    ):
        return _default_status(
            product,
            provider,
            "UNSUPPORTED_PRODUCT",
        )

    if not provider:
        return _default_status(
            product,
            provider,
            "PROVIDER_REQUIRED",
        )

    raw = load_config()

    if (
        raw.get(
            "schema_version"
        )
        != CONFIG_SCHEMA_VERSION
    ):
        return _default_status(
            product,
            provider,
            "LEGACY_OR_UNSCOPED_CONFIG_IGNORED",
        )

    providers = raw.get(
        "providers"
    )

    if not isinstance(
        providers,
        dict,
    ):
        return _default_status(
            product,
            provider,
            "PROVIDER_MAP_MISSING",
        )

    provider_block = (
        providers.get(
            provider
        )
    )

    if not isinstance(
        provider_block,
        dict,
    ):
        return _default_status(
            product,
            provider,
            "PROVIDER_CALIBRATION_MISSING",
        )

    record = (
        provider_block.get(
            product
        )
    )

    if not isinstance(
        record,
        dict,
    ):
        return _default_status(
            product,
            provider,
            "PRODUCT_CALIBRATION_MISSING",
        )

    actual_provider = (
        _provider(
            record.get(
                "calibration_provider"
            )
        )
    )

    if (
        actual_provider
        != provider
    ):
        return _default_status(
            product,
            provider,
            "CALIBRATION_PROVIDER_MISMATCH",
        )

    calibrated_at = _text(
        record.get(
            "calibrated_at"
        )
    )

    evidence_ref = _text(
        record.get(
            "evidence_ref"
        )
    )

    evidence_kind = _provider(
        record.get(
            "evidence_kind"
        )
    )

    if (
        not calibrated_at
        or not evidence_ref
        or evidence_kind
        != CALIBRATION_EVIDENCE_KIND
    ):
        return _default_status(
            product,
            provider,
            "LIVE_CALIBRATION_EVIDENCE_INCOMPLETE",
        )

    result = _default_status(
        product,
        provider,
        "OK",
    )

    result.update(
        record
    )

    result["product"] = (
        product
    )

    result[
        "calibration_provider"
    ] = provider

    result[
        "provider_scoped"
    ] = True

    result[
        "calibration_valid"
    ] = True

    result["reason"] = "OK"

    return result


def is_quantity_semantics_verified(
    product,
    provider=CANONICAL_EXECUTION_PROVIDER,
):
    record = (
        get_provider_product_config(
            product,
            provider,
        )
    )

    return bool(
        record.get(
            "calibration_valid"
        )
        and record.get(
            "depth_quantity_semantics_verified"
        )
        and _text(
            record.get(
                "depth_quantity_unit"
            )
        )
    )


def get_freshness_config(
    product,
    provider=CANONICAL_EXECUTION_PROVIDER,
):
    record = (
        get_provider_product_config(
            product,
            provider,
        )
    )

    if not record.get(
        "calibration_valid"
    ):
        return False, None

    if not record.get(
        "execution_freshness_calibrated"
    ):
        return False, None

    try:
        max_age = float(
            record.get(
                "execution_quote_max_age_seconds"
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return False, None

    if max_age <= 0:
        return False, None

    return True, max_age


def is_freshness_calibrated(
    product,
    provider=CANONICAL_EXECUTION_PROVIDER,
):
    ok, _ = (
        get_freshness_config(
            product,
            provider,
        )
    )

    return ok


def get_execution_quote_max_age_seconds(
    product,
    provider=CANONICAL_EXECUTION_PROVIDER,
):
    ok, age = (
        get_freshness_config(
            product,
            provider,
        )
    )

    return (
        age
        if ok
        else None
    )


def is_entry_execution_calibrated(
    product,
    provider=CANONICAL_EXECUTION_PROVIDER,
):
    return bool(
        is_quantity_semantics_verified(
            product,
            provider,
        )
        and
        is_freshness_calibrated(
            product,
            provider,
        )
    )


def calibration_status(
    product,
    provider=CANONICAL_EXECUTION_PROVIDER,
):
    record = (
        get_provider_product_config(
            product,
            provider,
        )
    )

    quantity_ok = (
        is_quantity_semantics_verified(
            product,
            provider,
        )
    )

    freshness_ok, max_age = (
        get_freshness_config(
            product,
            provider,
        )
    )

    return {
        "product":
            _product(product),
        "provider":
            _provider(provider),
        "provider_scoped":
            bool(
                record.get(
                    "provider_scoped"
                )
            ),
        "calibration_valid":
            bool(
                record.get(
                    "calibration_valid"
                )
            ),
        "quantity_verified":
            quantity_ok,
        "freshness_calibrated":
            freshness_ok,
        "max_age_seconds":
            max_age,
        "entry_execution_calibrated":
            bool(
                quantity_ok
                and freshness_ok
            ),
        "reason":
            record.get(
                "reason"
            ),
    }
