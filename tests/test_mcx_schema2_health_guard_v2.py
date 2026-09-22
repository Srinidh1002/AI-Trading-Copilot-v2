import json
import subprocess
import sys
from pathlib import Path

from mcx import mcx_version
from mcx.mcx_health import execution_health


def _write_config(
    root: Path,
    payload: dict,
) -> Path:
    path = root / "data" / "execution_evidence" / "mcx" / "exec_config.json"

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return path


def _provider_record() -> dict:
    return {
        "calibration_provider": "FYERS",
        "depth_quantity_semantics_verified": True,
        "depth_quantity_unit": "CONTRACT_UNITS",
        "execution_freshness_calibrated": True,
        "execution_quote_max_age_seconds": 10.0,
        "calibrated_at": "2026-09-22T20:58:00+05:30",
        "evidence_ref": "test-live-depth-proof",
        "evidence_kind": "LIVE_MARKET_DEPTH",
    }


def _legacy_ready_record() -> dict:
    return {
        "rest_depth_supported": True,
        "depth_quantity_semantics_verified": True,
        "execution_freshness_calibrated": True,
        "execution_quote_max_age_seconds": 12.0,
    }


def test_schema2_health_ignores_legacy_gold_authority(
    tmp_path,
    monkeypatch,
):
    _write_config(
        tmp_path,
        {
            "schema_version": 2,
            "providers": {
                "FYERS": {
                    "CRUDEOILM": _provider_record(),
                },
            },
            # Historical compatibility evidence intentionally remains.
            "CRUDEOILM": _legacy_ready_record(),
            "GOLDM": _legacy_ready_record(),
        },
    )

    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        mcx_version,
        "is_certification_eligible",
        lambda _product: False,
    )

    health = execution_health()

    assert health["freshness_CRUDEOILM"] == "PASS"

    assert health["qty_semantics_CRUDEOILM"] == "PASS"

    assert health["freshness_GOLDM"] == "UNCALIBRATED"

    assert health["qty_semantics_GOLDM"] == "UNVERIFIED"

    assert health["live_depth_verified_CRUDEOILM"] == "PASS_EXECUTION_PRECERT"

    assert health["live_depth_verified_GOLDM"] == "PENDING_LIVE_PROBE"

    assert health["live_depth_verified_SILVERM"] == "PENDING_LIVE_PROBE"

    assert health["live_depth_verified"] == "PENDING_LIVE_PROBE"


def test_schema1_health_retains_legacy_reporting(
    tmp_path,
    monkeypatch,
):
    _write_config(
        tmp_path,
        {
            "schema_version": "1.0",
            "GOLDM": _legacy_ready_record(),
        },
    )

    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        mcx_version,
        "is_certification_eligible",
        lambda _product: False,
    )

    health = execution_health()

    assert health["live_depth_verified_GOLDM"] == "PASS_EXECUTION_PRECERT"


def test_legacy_writer_is_fail_closed(
    tmp_path,
):
    repo = Path(__file__).resolve().parents[1]

    script = repo / "write_exec_config.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr

    assert result.returncode != 0

    assert "DEPRECATED_MCX_EXEC_CONFIG_WRITER" in combined

    assert not (
        tmp_path / "data" / "execution_evidence" / "mcx" / "exec_config.json"
    ).exists()
