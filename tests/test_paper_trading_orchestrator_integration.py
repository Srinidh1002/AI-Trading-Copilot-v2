"""
End-to-end integration tests for the paper-trading
orchestration subsystem.

Flow under test:

Pipeline Result
    ->
PaperTradingOrchestrator
    ->
PaperTradingEngine
    ->
PaperTradeRepository
    ->
Restart / Recovery

Paper trading only.
No real broker orders are placed.
"""

from services.paper_trade import (
    PaperTradeStatus,
)

from services.paper_trade_repository import (
    PaperTradeRepository,
)

from services.paper_trading_engine import (
    PaperTradingEngine,
)

from services.paper_trading_orchestrator import (
    PaperTradingOrchestrator,
)


# ============================================================
# HELPERS
# ============================================================


def make_pipeline_result(
    decision="TRADE_ALLOWED",
):
    """
    Build a valid pipeline result compatible with the
    real PaperTradingEngine.
    """

    return {
        "decision": decision,
        "direction": "BULLISH",
        "contract": {
            "selected": True,
            "symbol": "NIFTY_TEST_CE",
            "option_type": "CE",
            "strike": 24200.0,
            "premium": 100.0,
            "lot_size": 75,
            "expiry": "2026-07-30",
        },
        "trade_plan": {
            "allowed": (
                decision
                == "TRADE_ALLOWED"
            ),
            "decision": decision,
            "levels": {
                "option_entry_price": 100.0,
                "option_stop_loss": 80.0,
                "option_target": 140.0,
            },
            "risk": {
                "allowed": (
                    decision
                    == "TRADE_ALLOWED"
                ),
                "lots": 1,
                "quantity": 75,
                "required_capital": 7500.0,
                "estimated_maximum_loss": 1500.0,
            },
        },
    }


def make_system(
    tmp_path,
    *,
    enabled=True,
    persist_state=True,
):
    """
    Build a complete real paper-trading system.
    """

    repository_path = (
        tmp_path
        / "paper_trade_state.json"
    )

    repository = (
        PaperTradeRepository(
            repository_path
        )
    )

    engine = (
        PaperTradingEngine(
            repository=repository,
            persist_state=persist_state,
        )
    )

    orchestrator = (
        PaperTradingOrchestrator(
            paper_trading_engine=engine,
            enabled=enabled,
        )
    )

    return {
        "repository_path": (
            repository_path
        ),
        "repository": repository,
        "engine": engine,
        "orchestrator": orchestrator,
    }


def process_trade(
    orchestrator,
    *,
    source_decision_id="decision-001",
    trade_id="paper-trade-001",
):
    """
    Process one deterministic TRADE_ALLOWED result.
    """

    return (
        orchestrator.process_decision(
            pipeline_result=(
                make_pipeline_result()
            ),
            underlying="NIFTY",
            exchange="NSE",
            symboltoken="99926000",
            source_decision_id=(
                source_decision_id
            ),
            source_audit_ref=(
                "audit-001"
            ),
            opened_at=(
                "2026-07-12T09:15:00+00:00"
            ),
            metadata={
                "integration_test": True,
            },
            trade_id=trade_id,
        )
    )


# ============================================================
# DECISION -> REAL ENGINE
# ============================================================


def test_allowed_decision_opens_real_paper_trade(
    tmp_path,
):

    system = make_system(
        tmp_path
    )

    result = process_trade(
        system["orchestrator"]
    )

    assert (
        result["status"]
        == "OPENED"
    )

    assert (
        result["opened"]
        is True
    )

    assert (
        result["trade_id"]
        == "paper-trade-001"
    )

    assert (
        system["engine"].count_trades()
        == 1
    )

    assert (
        system["engine"].count_open_trades()
        == 1
    )


def test_real_trade_contains_source_decision_reference(
    tmp_path,
):

    system = make_system(
        tmp_path
    )

    process_trade(
        system["orchestrator"],
        source_decision_id=(
            "source-decision-123"
        ),
    )

    trade = (
        system["engine"].get_trade(
            "paper-trade-001"
        )
    )

    assert (
        trade.source_decision_id
        == "source-decision-123"
    )


def test_real_trade_contains_source_audit_reference(
    tmp_path,
):

    system = make_system(
        tmp_path
    )

    process_trade(
        system["orchestrator"]
    )

    trade = (
        system["engine"].get_trade(
            "paper-trade-001"
        )
    )

    assert (
        trade.source_audit_ref
        == "audit-001"
    )


def test_real_trade_contains_orchestrator_metadata(
    tmp_path,
):

    system = make_system(
        tmp_path
    )

    process_trade(
        system["orchestrator"]
    )

    trade = (
        system["engine"].get_trade(
            "paper-trade-001"
        )
    )

    assert (
        trade.metadata[
            "orchestrated_by"
        ]
        == "PaperTradingOrchestrator"
    )

    assert (
        trade.metadata[
            "paper_trade"
        ]
        is True
    )

    assert (
        trade.metadata[
            "integration_test"
        ]
        is True
    )


# ============================================================
# NON-TRADE SAFETY
# ============================================================


def test_non_trade_decision_does_not_open_real_trade(
    tmp_path,
):

    system = make_system(
        tmp_path
    )

    result = (
        system[
            "orchestrator"
        ].process_decision(
            pipeline_result=(
                make_pipeline_result(
                    decision="NO_TRADE"
                )
            ),
            underlying="NIFTY",
            exchange="NSE",
            symboltoken="99926000",
            source_decision_id=(
                "no-trade-decision"
            ),
        )
    )

    assert (
        result["status"]
        == "SKIPPED"
    )

    assert (
        system["engine"].count_trades()
        == 0
    )


def test_disabled_orchestrator_does_not_open_real_trade(
    tmp_path,
):

    system = make_system(
        tmp_path,
        enabled=False,
    )

    result = process_trade(
        system["orchestrator"]
    )

    assert (
        result["status"]
        == "SKIPPED"
    )

    assert (
        result["reason"]
        == "PAPER_TRADING_DISABLED"
    )

    assert (
        system["engine"].count_trades()
        == 0
    )


# ============================================================
# DUPLICATE PROTECTION
# ============================================================


def test_duplicate_decision_does_not_open_second_trade(
    tmp_path,
):

    system = make_system(
        tmp_path
    )

    first = process_trade(
        system["orchestrator"],
        source_decision_id=(
            "duplicate-decision"
        ),
        trade_id="trade-one",
    )

    second = process_trade(
        system["orchestrator"],
        source_decision_id=(
            "duplicate-decision"
        ),
        trade_id="trade-two",
    )

    assert (
        first["status"]
        == "OPENED"
    )

    assert (
        second["status"]
        == "SKIPPED"
    )

    assert (
        second["reason"]
        == "DUPLICATE_SOURCE_DECISION"
    )

    assert (
        system["engine"].count_trades()
        == 1
    )


def test_different_decisions_open_different_trades(
    tmp_path,
):

    system = make_system(
        tmp_path
    )

    first = process_trade(
        system["orchestrator"],
        source_decision_id="decision-one",
        trade_id="trade-one",
    )

    second = process_trade(
        system["orchestrator"],
        source_decision_id="decision-two",
        trade_id="trade-two",
    )

    assert (
        first["status"]
        == "OPENED"
    )

    assert (
        second["status"]
        == "OPENED"
    )

    assert (
        system["engine"].count_trades()
        == 2
    )


# ============================================================
# PERSISTENCE
# ============================================================


def test_orchestrated_trade_is_persisted(
    tmp_path,
):

    system = make_system(
        tmp_path
    )

    result = process_trade(
        system["orchestrator"]
    )

    persisted = (
        system[
            "repository"
        ].get_trade(
            result["trade_id"]
        )
    )

    assert persisted is not None

    assert (
        persisted["trade_id"]
        == "paper-trade-001"
    )

    assert (
        persisted["status"]
        == PaperTradeStatus.OPEN
    )


def test_orchestrated_trade_update_is_persisted(
    tmp_path,
):

    system = make_system(
        tmp_path
    )

    result = process_trade(
        system["orchestrator"]
    )

    updated = (
        system[
            "engine"
        ].update_price(
            trade_id=(
                result["trade_id"]
            ),
            current_price=120.0,
            updated_at=(
                "2026-07-12T09:30:00+00:00"
            ),
        )
    )

    persisted = (
        system[
            "repository"
        ].get_trade(
            result["trade_id"]
        )
    )

    assert (
        updated.current_price
        == 120.0
    )

    assert (
        persisted[
            "current_price"
        ]
        == 120.0
    )


def test_orchestrated_trade_close_is_persisted(
    tmp_path,
):

    system = make_system(
        tmp_path
    )

    result = process_trade(
        system["orchestrator"]
    )

    closed = (
        system[
            "engine"
        ].close_trade(
            trade_id=(
                result["trade_id"]
            ),
            exit_price=120.0,
            closed_at=(
                "2026-07-12T10:00:00+00:00"
            ),
        )
    )

    persisted = (
        system[
            "repository"
        ].get_trade(
            result["trade_id"]
        )
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        persisted["status"]
        == PaperTradeStatus.CLOSED
    )

    assert (
        persisted["exit_price"]
        == 120.0
    )


# ============================================================
# STOP LOSS / TARGET
# ============================================================


def test_orchestrated_trade_can_hit_stop_loss(
    tmp_path,
):

    system = make_system(
        tmp_path
    )

    result = process_trade(
        system["orchestrator"]
    )

    trade = (
        system[
            "engine"
        ].update_price(
            trade_id=(
                result["trade_id"]
            ),
            current_price=80.0,
        )
    )

    assert (
        trade.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        system["engine"].count_open_trades()
        == 0
    )

    assert (
        system["engine"].count_closed_trades()
        == 1
    )


def test_orchestrated_trade_can_hit_target(
    tmp_path,
):

    system = make_system(
        tmp_path
    )

    result = process_trade(
        system["orchestrator"]
    )

    trade = (
        system[
            "engine"
        ].update_price(
            trade_id=(
                result["trade_id"]
            ),
            current_price=140.0,
        )
    )

    assert (
        trade.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        system["engine"].count_closed_trades()
        == 1
    )


# ============================================================
# RESTART RECOVERY
# ============================================================


def test_orchestrated_trade_survives_restart(
    tmp_path,
):

    first_system = make_system(
        tmp_path
    )

    result = process_trade(
        first_system[
            "orchestrator"
        ]
    )

    trade_id = (
        result["trade_id"]
    )

    # Simulated process restart:
    # create completely new repository,
    # engine and orchestrator instances.

    second_repository = (
        PaperTradeRepository(
            first_system[
                "repository_path"
            ]
        )
    )

    second_engine = (
        PaperTradingEngine(
            repository=(
                second_repository
            ),
            persist_state=True,
        )
    )

    second_orchestrator = (
        PaperTradingOrchestrator(
            paper_trading_engine=(
                second_engine
            ),
            enabled=True,
        )
    )

    recovered = (
        second_engine.recover_trades()
    )

    assert len(
        recovered
    ) == 1

    recovered_trade = (
        second_engine.get_trade(
            trade_id
        )
    )

    assert (
        recovered_trade.trade_id
        == trade_id
    )

    assert (
        recovered_trade.status
        == PaperTradeStatus.OPEN
    )

    # Confirm the new orchestrator and recovered
    # engine coexist correctly.

    assert (
        second_orchestrator.enabled
        is True
    )


def test_recovered_orchestrated_trade_can_continue(
    tmp_path,
):

    first_system = make_system(
        tmp_path
    )

    result = process_trade(
        first_system[
            "orchestrator"
        ],
        trade_id="restart-trade",
    )

    second_repository = (
        PaperTradeRepository(
            first_system[
                "repository_path"
            ]
        )
    )

    second_engine = (
        PaperTradingEngine(
            repository=(
                second_repository
            ),
            persist_state=True,
        )
    )

    second_engine.recover_trades()

    updated = (
        second_engine.update_price(
            trade_id=(
                result["trade_id"]
            ),
            current_price=125.0,
        )
    )

    assert (
        updated.status
        == PaperTradeStatus.OPEN
    )

    assert (
        updated.current_price
        == 125.0
    )


def test_recovered_orchestrated_trade_can_close(
    tmp_path,
):

    first_system = make_system(
        tmp_path
    )

    result = process_trade(
        first_system[
            "orchestrator"
        ],
        trade_id=(
            "restart-close-trade"
        ),
    )

    second_repository = (
        PaperTradeRepository(
            first_system[
                "repository_path"
            ]
        )
    )

    second_engine = (
        PaperTradingEngine(
            repository=(
                second_repository
            ),
            persist_state=True,
        )
    )

    second_engine.recover_trades()

    closed = (
        second_engine.close_trade(
            trade_id=(
                result["trade_id"]
            ),
            exit_price=130.0,
        )
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )


# ============================================================
# MULTIPLE TRADE RECOVERY
# ============================================================


def test_multiple_orchestrated_trades_survive_restart(
    tmp_path,
):

    first_system = make_system(
        tmp_path
    )

    process_trade(
        first_system[
            "orchestrator"
        ],
        source_decision_id=(
            "decision-one"
        ),
        trade_id="trade-one",
    )

    process_trade(
        first_system[
            "orchestrator"
        ],
        source_decision_id=(
            "decision-two"
        ),
        trade_id="trade-two",
    )

    second_engine = (
        PaperTradingEngine(
            repository=(
                PaperTradeRepository(
                    first_system[
                        "repository_path"
                    ]
                )
            ),
            persist_state=True,
        )
    )

    recovered = (
        second_engine.recover_trades()
    )

    assert len(
        recovered
    ) == 2

    assert (
        second_engine.count_open_trades()
        == 2
    )


# ============================================================
# PERSISTENCE DISABLED
# ============================================================


def test_orchestration_works_with_persistence_disabled(
    tmp_path,
):

    system = make_system(
        tmp_path,
        persist_state=False,
    )

    result = process_trade(
        system["orchestrator"]
    )

    assert (
        result["status"]
        == "OPENED"
    )

    assert (
        system["engine"].count_trades()
        == 1
    )

    assert (
        system[
            "repository"
        ].get_trade(
            result["trade_id"]
        )
        is None
    )


# ============================================================
# FULL LIFECYCLE
# ============================================================


def test_complete_decision_to_restart_lifecycle(
    tmp_path,
):

    # --------------------------------------------------------
    # 1. CREATE SYSTEM
    # --------------------------------------------------------

    first_system = make_system(
        tmp_path
    )

    # --------------------------------------------------------
    # 2. PROCESS TRADE_ALLOWED
    # --------------------------------------------------------

    orchestration_result = (
        process_trade(
            first_system[
                "orchestrator"
            ],
            source_decision_id=(
                "full-lifecycle-decision"
            ),
            trade_id=(
                "full-lifecycle-trade"
            ),
        )
    )

    assert (
        orchestration_result[
            "status"
        ]
        == "OPENED"
    )

    # --------------------------------------------------------
    # 3. UPDATE POSITION
    # --------------------------------------------------------

    updated = (
        first_system[
            "engine"
        ].update_price(
            trade_id=(
                "full-lifecycle-trade"
            ),
            current_price=120.0,
        )
    )

    assert (
        updated.status
        == PaperTradeStatus.OPEN
    )

    # --------------------------------------------------------
    # 4. SIMULATE RESTART
    # --------------------------------------------------------

    restarted_engine = (
        PaperTradingEngine(
            repository=(
                PaperTradeRepository(
                    first_system[
                        "repository_path"
                    ]
                )
            ),
            persist_state=True,
        )
    )

    restarted_engine.recover_trades()

    recovered = (
        restarted_engine.get_trade(
            "full-lifecycle-trade"
        )
    )

    assert (
        recovered.current_price
        == 120.0
    )

    # --------------------------------------------------------
    # 5. HIT TARGET AFTER RESTART
    # --------------------------------------------------------

    closed = (
        restarted_engine.update_price(
            trade_id=(
                "full-lifecycle-trade"
            ),
            current_price=140.0,
        )
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    # --------------------------------------------------------
    # 6. VERIFY FINAL PERSISTED STATE
    # --------------------------------------------------------

    final_repository = (
        PaperTradeRepository(
            first_system[
                "repository_path"
            ]
        )
    )

    persisted = (
        final_repository.get_trade(
            "full-lifecycle-trade"
        )
    )

    assert (
        persisted["status"]
        == PaperTradeStatus.CLOSED
    )

    assert (
        persisted["current_price"]
        == 140.0
    )

    assert (
        persisted["exit_price"]
        == 140.0
    )