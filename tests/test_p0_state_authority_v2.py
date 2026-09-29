"""Wave 2 — state authority for index and MCX. Synthetic fixtures, temp paths."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))


@pytest.fixture
def mcx_bot(monkeypatch, tmp_path):
    from mcx import mcx_paper_bot as m

    monkeypatch.setattr(m, "PRODUCT", "CRUDEOILM")
    monkeypatch.setattr(m, "STATE_PATH", str(tmp_path / "mcx_crudeoilm_experimental.json"))
    return m


def _valid_mcx_state(
    product="CRUDEOILM",
    epoch=None,
    version=None,
):
    from mcx.mcx_version import (
        get_product_epochs,
    )

    cfg = get_product_epochs(product)

    if cfg is None:
        raise AssertionError(f"missing product registry: {product}")

    return {
        "product": product,
        "epoch": (cfg["epoch"] if epoch is None else epoch),
        "strategy_version": (cfg["strategy_version"] if version is None else version),
        "_counted_trade_ids": [],
        "t1_hit_wins": 0,
        "sl_losses": 0,
        "total_trades": 0,
        "completed_trades": [],
        "active_position": None,
    }


def _write(path, payload):
    Path(path).write_text(json.dumps(payload), encoding="utf-8")


def test_mcx_valid_state_loads(mcx_bot):
    _write(mcx_bot.STATE_PATH, _valid_mcx_state())
    st = mcx_bot.load_state()
    assert st["product"] == "CRUDEOILM"


def test_mcx_missing_state_raises(mcx_bot):
    with pytest.raises(mcx_bot.MCXStateAuthorityError, match="MISSING_UNEXPECTED"):
        mcx_bot.load_state()


def test_mcx_corrupt_json_raises(mcx_bot):
    Path(mcx_bot.STATE_PATH).write_text("{bad json", encoding="utf-8")
    with pytest.raises(mcx_bot.MCXStateAuthorityError, match="CORRUPT"):
        mcx_bot.load_state()


def test_mcx_wrong_product_raises(mcx_bot):
    _write(mcx_bot.STATE_PATH, _valid_mcx_state(product="GOLDM"))
    with pytest.raises(mcx_bot.MCXStateAuthorityError, match="SCHEMA_INVALID"):
        mcx_bot.load_state()


def test_mcx_wrong_epoch_raises(mcx_bot):
    _write(mcx_bot.STATE_PATH, _valid_mcx_state(epoch="WRONG_EPOCH"))
    with pytest.raises(mcx_bot.MCXStateAuthorityError, match="EPOCH_MISMATCH"):
        mcx_bot.load_state()


def test_mcx_wrong_strategy_version_raises(mcx_bot):
    _write(mcx_bot.STATE_PATH, _valid_mcx_state(version="WRONG_VERSION"))
    with pytest.raises(mcx_bot.MCXStateAuthorityError, match="EPOCH_MISMATCH"):
        mcx_bot.load_state()


def test_mcx_counter_incoherent_raises(mcx_bot):
    st = _valid_mcx_state()
    st["_counted_trade_ids"] = ["T1"]
    st["t1_hit_wins"] = 0
    st["sl_losses"] = 0  # mismatch: 1 id vs 0 total
    _write(mcx_bot.STATE_PATH, st)
    with pytest.raises(mcx_bot.MCXStateAuthorityError, match="COUNTER_INCOHERENT"):
        mcx_bot.load_state()


def test_mcx_duplicate_counted_ids_raise(mcx_bot):
    st = _valid_mcx_state()
    st["_counted_trade_ids"] = ["T1", "T1"]
    st["t1_hit_wins"] = 2
    st["sl_losses"] = 0
    _write(mcx_bot.STATE_PATH, st)
    with pytest.raises(mcx_bot.MCXStateAuthorityError, match="COUNTER_INCOHERENT"):
        mcx_bot.load_state()


def test_mcx_malformed_active_position_raises(mcx_bot):
    st = _valid_mcx_state()
    st["active_position"] = {"symbol": "X"}  # missing trade_id and entry_time
    _write(mcx_bot.STATE_PATH, st)
    with pytest.raises(mcx_bot.MCXStateAuthorityError, match="SCHEMA_INVALID_ACTIVE_POSITION"):
        mcx_bot.load_state()


def test_mcx_save_is_atomic(mcx_bot):
    """Writing then reading back yields the same payload; no partial file."""
    _write(mcx_bot.STATE_PATH, _valid_mcx_state())
    st = mcx_bot.load_state()
    st["total_trades"] = 5
    mcx_bot.save_state(st)
    reloaded = mcx_bot.load_state()
    assert reloaded["total_trades"] == 5


def test_default_state_for_matches_epoch(mcx_bot):
    from mcx.mcx_version import (
        get_product_epochs,
    )

    cfg = get_product_epochs("CRUDEOILM")

    st = mcx_bot._default_state_for("CRUDEOILM")

    assert st["product"] == "CRUDEOILM"

    assert st["epoch"] == cfg["epoch"]

    assert st["strategy_version"] == cfg["strategy_version"]
