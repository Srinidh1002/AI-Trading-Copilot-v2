"""PATCH04 — three-product MCX offline lifecycle proof.

Pure/offline proof only:
- no credentials;
- no provider network;
- no runtime state writes;
- no quote recorder writes;
- no outcome ledger writes;
- no certification counter credit.

The proof exercises the real production lifecycle, fill, reconciliation,
position-management and countability components with deterministic FYERS-shaped
execution evidence.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import pytest

from mcx.mcx_certification import (
    update_counters,
)
from mcx.mcx_contracts import (
    PRODUCTS,
)
from mcx.mcx_exec_countability import (
    is_countable,
)
from mcx.mcx_exec_fill import (
    compute_paper_fill_v2,
)
from mcx.mcx_exec_first_touch import (
    FirstTouchTracker,
)
from mcx.mcx_exec_lifecycle import (
    apply_transition,
    transition,
)
from mcx.mcx_exec_quote import (
    make_execution_quote,
    validate_quote,
)
from mcx.mcx_position_manager import (
    evaluate_exit,
)
from mcx.mcx_reconcile import (
    reconcile,
)
from mcx.mcx_version import (
    get_product_epochs,
)


PRODUCTS_UNDER_TEST = (
    "CRUDEOILM",
    "GOLDM",
    "SILVERM",
)


STRIKES = {
    "CRUDEOILM": 9500.0,
    "GOLDM": 125000.0,
    "SILVERM": 180000.0,
}


def _quote(
    product,
    *,
    token,
    bid,
    ask,
    received_at,
):
    qty = max(
        1000,
        int(
            PRODUCTS[
                product
            ]["trading_unit"]
        )
        * 20,
    )

    quote = make_execution_quote(
        product=product,
        option_symbol=(
            f"MCX:{product}_OFFLINE_CE"
        ),
        token=token,
        exchange="MCX",
        option_type="CE",
        strike=STRIKES[product],
        expiry="2026-09-25",
        ltp=(bid + ask) / 2,
        bids=[
            {
                "price": bid,
                "quantity": qty,
                "orders": 5,
            }
        ],
        asks=[
            {
                "price": ask,
                "quantity": qty,
                "orders": 5,
            }
        ],
        volume=5000,
        open_interest=25000,
        exchange_feed_time=(
            "2026-09-18T10:00:00+05:30"
        ),
        exchange_trade_time=(
            "2026-09-18T10:00:00+05:30"
        ),
        provider_received_at=received_at,
        provider="FYERS",
        source_mode="REST_FULL",
        tick_size=(
            PRODUCTS[
                product
            ]["option_tick_size"]
        ),
        raw_payload={
            "provider": "FYERS",
            "product": product,
            "token": token,
            "bid": bid,
            "ask": ask,
        },
    )

    ok, checked = validate_quote(
        quote,
        expected_token=token,
        expected_exchange="MCX",
        now_iso=(
            "2026-09-18T10:00:01+05:30"
        ),
        max_age_seconds=5.0,
    )

    assert ok is True
    assert (
        checked[
            "validation_status"
        ]
        == "VALID"
    )

    assert (
        checked["provider"]
        == "FYERS"
    )

    return checked


def _apply(
    position,
    new_state,
    reason,
):
    current = position[
        "lifecycle_state"
    ]

    event = transition(
        current,
        new_state,
        reason,
        timestamp_iso=(
            "2026-09-18T10:00:00+05:30"
        ),
    )

    apply_transition(
        position,
        event,
    )


def _run_product_lifecycle(
    product,
):
    cfg = get_product_epochs(
        product
    )

    assert cfg is not None

    spec = PRODUCTS[
        product
    ]

    token = (
        f"FYERS-{product}-CE"
    )

    tick = float(
        spec["option_tick_size"]
    )

    requested_qty = int(
        spec["trading_unit"]
    )

    # -----------------------------------------------------------------
    # FLAT -> ENTRY CANDIDATE
    # -----------------------------------------------------------------

    pos = {
        "product": product,
        "lifecycle_state": "FLAT",
        "lifecycle_history": [],
    }

    _apply(
        pos,
        "ENTRY_CANDIDATE",
        "OFFLINE_VALID_CANDIDATE",
    )

    # -----------------------------------------------------------------
    # FYERS execution evidence -> BUY depth-VWAP
    # -----------------------------------------------------------------

    entry_quote = _quote(
        product,
        token=token,
        bid=99.50,
        ask=100.00,
        received_at=(
            "2026-09-18T10:00:00+05:30"
        ),
    )

    _apply(
        pos,
        "EXECUTION_QUOTE_VALIDATED",
        "FYERS_ENTRY_DEPTH_VALID",
    )

    entry_fill = (
        compute_paper_fill_v2(
            entry_quote,
            "BUY",
            requested_qty,
            tick=tick,
        )
    )

    assert (
        entry_fill["status"]
        == "OK"
    )

    assert (
        entry_fill["fill_method"]
        == "DEPTH_VWAP"
    )

    entry = float(
        entry_fill["fill_price"]
    )

    pos.update({
        "trade_id":
            f"OFFLINE_{product}_001",
        "epoch_id":
            cfg["epoch"],
        "strategy_version":
            cfg["strategy_version"],
        "certification_eligible":
            bool(
                cfg[
                    "certification_eligible"
                ]
            ),
        "type":
            "CE",
        "strike":
            STRIKES[product],
        "token":
            token,
        "symbol":
            f"MCX:{product}_OFFLINE_CE",
        "entry":
            entry,
        "entry_time":
            "2026-09-18T10:00:00+05:30",
        "lots":
            1,
        "lot_size":
            spec["trading_unit"],
        "cash_multiplier":
            spec["cash_multiplier"],
        "stop_loss":
            round(
                entry * 0.92,
                2,
            ),
        "t1":
            round(
                entry * 1.15,
                2,
            ),
        "t2":
            round(
                entry * 1.30,
                2,
            ),
        "t3":
            round(
                entry * 1.50,
                2,
            ),
        "max_profit_pct":
            0.0,
        "min_profit_pct":
            0.0,
        "execution_mode":
            "PAPER",
        "market_origin":
            "REAL_MARKET",
        "quote_origin":
            "REAL_PROVIDER",
        "entry_quote_id":
            entry_quote[
                "raw_payload_hash"
            ],
        "entry_quote_stale":
            False,
        "entry_fill_method":
            "DEPTH_VWAP",
        "entry_levels_consumed":
            entry_fill[
                "levels_consumed"
            ],
        "entry_source_mode":
            "REST_FULL",
        "lifecycle_evidence_complete":
            True,
        "terminal":
            False,
        "reconciled":
            False,
    })

    _apply(
        pos,
        "PAPER_OPEN",
        "OFFLINE_PAPER_FILL",
    )

    _apply(
        pos,
        "MONITORING",
        "OFFLINE_MONITOR_START",
    )

    # -----------------------------------------------------------------
    # Position-management HOLD/profit-protection path
    # -----------------------------------------------------------------

    mark = round(
        entry * 1.10,
        2,
    )

    pos[
        "max_profit_pct"
    ] = 10.0

    pos[
        "min_profit_pct"
    ] = -1.0

    should_exit, reason, new_stop = (
        evaluate_exit(
            pos,
            mark,
            {
                "action": "BUY_CALL",
                "LONG_CONFIDENCE": 80,
                "SHORT_CONFIDENCE": 10,
            },
            {
                "regime": "TREND",
            },
            10,
        )
    )

    assert (
        should_exit
        is False
    )

    assert reason == "HOLD"

    assert (
        new_stop
        is not None
    )

    assert (
        new_stop
        > pos["stop_loss"]
    )

    pos["stop_loss"] = (
        new_stop
    )

    # -----------------------------------------------------------------
    # First-touch authority -> T1 first
    # -----------------------------------------------------------------

    tracker = FirstTouchTracker(
        t1_price=pos["t1"],
        sl_price=(
            round(
                entry * 0.92,
                2,
            )
        ),
    )

    tracker.ingest(
        round(
            pos["t1"] + tick,
            2,
        ),
        "2026-09-18T10:05:00+05:30",
        quote_id=(
            f"MONITOR_{product}_001"
        ),
    )

    pos[
        "first_touch_result"
    ] = tracker.result()

    pos[
        "first_touch_state"
    ] = tracker.to_state()

    assert (
        pos[
            "first_touch_result"
        ]
        == "T1_FIRST"
    )

    _apply(
        pos,
        "EXIT_TRIGGERED",
        "T1_FIRST",
    )

    # -----------------------------------------------------------------
    # FYERS exit depth -> SELL depth-VWAP
    # -----------------------------------------------------------------

    exit_bid = round(
        entry * 1.16,
        2,
    )

    exit_ask = round(
        exit_bid + tick,
        2,
    )

    exit_quote = _quote(
        product,
        token=token,
        bid=exit_bid,
        ask=exit_ask,
        received_at=(
            "2026-09-18T10:00:00+05:30"
        ),
    )

    _apply(
        pos,
        "EXIT_QUOTE_VALIDATED",
        "FYERS_EXIT_DEPTH_VALID",
    )

    exit_fill = (
        compute_paper_fill_v2(
            exit_quote,
            "SELL",
            requested_qty,
            tick=tick,
        )
    )

    assert (
        exit_fill["status"]
        == "OK"
    )

    assert (
        exit_fill["fill_method"]
        == "DEPTH_VWAP"
    )

    exit_price = float(
        exit_fill["fill_price"]
    )

    assert (
        exit_price
        > entry
    )

    pos.update({
        "exit":
            exit_price,
        "exit_quote_id":
            exit_quote[
                "raw_payload_hash"
            ],
        "exit_quote_stale":
            False,
        "exit_fill_method":
            "DEPTH_VWAP",
        "exit_levels_consumed":
            exit_fill[
                "levels_consumed"
            ],
        "exit_time":
            "2026-09-18T10:05:01+05:30",
        "exit_reason":
            "T1_FIRST",
        "terminal":
            True,
        "last_pnl_pct":
            round(
                (
                    (
                        exit_price
                        - entry
                    )
                    / entry
                )
                * 100,
                2,
            ),
    })

    _apply(
        pos,
        "PAPER_CLOSED",
        "OFFLINE_EXIT_FILLED",
    )

    _apply(
        pos,
        "RECONCILING",
        "OFFLINE_RECONCILE_START",
    )

    # -----------------------------------------------------------------
    # Reconciliation must use current product registry epoch/version.
    # -----------------------------------------------------------------

    reconciled = reconcile(
        pos,
        product=product,
    )

    assert (
        reconciled["status"]
        if "status" in reconciled
        else "OK"
    ) not in (
        "INCOMPLETE",
        "COST_ERROR",
    )

    reconciled[
        "reconciled"
    ] = True

    assert (
        reconciled["epoch_id"]
        == cfg["epoch"]
    )

    assert (
        reconciled[
            "strategy_version"
        ]
        == cfg[
            "strategy_version"
        ]
    )

    assert (
        reconciled[
            "registry_certification_eligible"
        ]
        is bool(
            cfg[
                "certification_eligible"
            ]
        )
    )

    assert (
        reconciled["net_pnl"]
        is not None
    )

    _apply(
        reconciled,
        "RECONCILED",
        "OFFLINE_RECONCILED",
    )

    # -----------------------------------------------------------------
    # FYERS execution calibration is intentionally absent before live
    # observation, so NONE of these offline trades may count.
    # -----------------------------------------------------------------

    countable, reasons = (
        is_countable(
            reconciled,
            product=product,
            known_trade_ids=set(),
        )
    )

    assert countable is False

    assert (
        "EXECUTION_FRESHNESS_UNCALIBRATED"
        in reasons
    )

    assert (
        "DEPTH_QUANTITY_SEMANTICS_UNVERIFIED"
        in reasons
    )

    reconciled[
        "certification_eligible"
    ] = False

    reconciled[
        "_countability_reasons"
    ] = reasons

    _apply(
        reconciled,
        "NON_COUNTABLE",
        "FYERS_LIVE_CALIBRATION_PENDING",
    )

    # -----------------------------------------------------------------
    # Certification counters must remain zero.
    # -----------------------------------------------------------------

    counter_state = {
        "product": product,
        "t1_hit_wins": 0,
        "sl_losses": 0,
        "_counted_trade_ids": [],
        "_cert_rejected_trade_ids": [],
        "completed_trades": [
            reconciled
        ],
    }

    update_counters(
        counter_state,
        reconciled,
    )

    assert (
        counter_state[
            "t1_hit_wins"
        ]
        == 0
    )

    assert (
        counter_state[
            "sl_losses"
        ]
        == 0
    )

    assert (
        counter_state[
            "_counted_trade_ids"
        ]
        == []
    )

    return {
        "product":
            product,
        "entry":
            entry,
        "exit":
            exit_price,
        "net_pnl":
            reconciled[
                "net_pnl"
            ],
        "epoch":
            reconciled[
                "epoch_id"
            ],
        "strategy_version":
            reconciled[
                "strategy_version"
            ],
        "countable":
            countable,
        "countability_reasons":
            reasons,
        "lifecycle_state":
            reconciled[
                "lifecycle_state"
            ],
        "lifecycle_history":
            reconciled[
                "lifecycle_history"
            ],
    }


@pytest.mark.parametrize(
    "product",
    PRODUCTS_UNDER_TEST,
)
def test_three_product_full_offline_lifecycle(
    product,
):
    result = (
        _run_product_lifecycle(
            product
        )
    )

    assert (
        result[
            "lifecycle_state"
        ]
        == "NON_COUNTABLE"
    )

    assert (
        result["countable"]
        is False
    )

    assert (
        result["exit"]
        > result["entry"]
    )

    states = [
        event[
            "state_after"
        ]
        for event
        in result[
            "lifecycle_history"
        ]
    ]

    assert states == [
        "ENTRY_CANDIDATE",
        "EXECUTION_QUOTE_VALIDATED",
        "PAPER_OPEN",
        "MONITORING",
        "EXIT_TRIGGERED",
        "EXIT_QUOTE_VALIDATED",
        "PAPER_CLOSED",
        "RECONCILING",
        "RECONCILED",
        "NON_COUNTABLE",
    ]


@pytest.mark.parametrize(
    "product",
    PRODUCTS_UNDER_TEST,
)
def test_reconciliation_uses_current_product_registry(
    product,
):
    cfg = get_product_epochs(
        product
    )

    rec = reconcile(
        {
            "trade_id":
                f"REGISTRY_{product}",
            "product":
                product,
            "entry":
                100.0,
            "exit":
                110.0,
            "lots":
                1,
            "entry_time":
                "2026-09-18T10:00:00+05:30",
            "exit_time":
                "2026-09-18T10:05:00+05:30",
            "exit_reason":
                "OFFLINE_TEST",
            "type":
                "CE",
            "strike":
                STRIKES[product],
            "max_profit_pct":
                10.0,
            "min_profit_pct":
                -1.0,
            "first_touch_result":
                "T1_FIRST",
            "terminal":
                True,
            "reconciled":
                True,
            "execution_mode":
                "PAPER",
            "market_origin":
                "REAL_MARKET",
            "quote_origin":
                "REAL_PROVIDER",
            "entry_fill_method":
                "DEPTH_VWAP",
            "exit_fill_method":
                "DEPTH_VWAP",
        },
        product=product,
    )

    assert (
        rec["epoch_id"]
        == cfg["epoch"]
    )

    assert (
        rec[
            "strategy_version"
        ]
        == cfg[
            "strategy_version"
        ]
    )


def test_crude_uses_current_v4_not_stale_v2():
    cfg = get_product_epochs(
        "CRUDEOILM"
    )

    assert (
        cfg["epoch"]
        == "POST_PRECISION_V4"
    )

    rec = reconcile(
        {
            "trade_id":
                "CRUDE_V4_PROOF",
            "product":
                "CRUDEOILM",
            "entry":
                100.0,
            "exit":
                110.0,
            "lots":
                1,
        },
        product="CRUDEOILM",
    )

    assert (
        rec["epoch_id"]
        == "POST_PRECISION_V4"
    )

    assert (
        rec[
            "strategy_version"
        ]
        == "MCX_POST_PRECISION_V4"
    )

    assert (
        "POST_PRECISION_V2"
        not in rec["epoch_id"]
    )


def test_gold_and_silver_remain_precert():
    for product in (
        "GOLDM",
        "SILVERM",
    ):
        cfg = get_product_epochs(
            product
        )

        assert (
            cfg[
                "certification_eligible"
            ]
            is False
        )

        result = (
            _run_product_lifecycle(
                product
            )
        )

        assert (
            result["countable"]
            is False
        )


def test_offline_proof_contains_no_order_authority():
    """Inspect Python structure instead of matching our own test strings."""
    import ast
    from pathlib import Path

    source = Path(
        "tests/"
        "test_mcx_three_product_offline_lifecycle_v2.py"
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    imported_modules = set()
    referenced_names = set()
    referenced_attributes = set()

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                imported_modules.add(
                    alias.name
                )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module:
                imported_modules.add(
                    node.module
                )

            for alias in node.names:
                referenced_names.add(
                    alias.name
                )

        elif isinstance(
            node,
            ast.Name,
        ):
            referenced_names.add(
                node.id
            )

        elif isinstance(
            node,
            ast.Attribute,
        ):
            referenced_attributes.add(
                node.attr
            )

    assert not any(
        module.lower().startswith(
            "smartapi"
        )
        for module in imported_modules
    )

    assert "pyotp" not in imported_modules

    forbidden_symbols = {
        "SmartConnect",
        "placeOrder",
        "place_order",
        "modifyOrder",
        "modify_order",
        "cancelOrder",
        "cancel_order",
        "FyersOrderSocket",
    }

    actual_symbols = (
        referenced_names
        | referenced_attributes
    )

    assert not (
        forbidden_symbols
        & actual_symbols
    )