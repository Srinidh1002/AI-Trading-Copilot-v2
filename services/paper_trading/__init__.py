"""Public exports for PAPER-only trade lifecycle services.

The legacy PaperTradingEngine adapter is exposed lazily so importing
the P7 evaluator, persistence service, recovery service, or replay
coordinator does not load the legacy paper-trading engine.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    "evaluate_paper_trade_entry": (
        "services.paper_trading.paper_trade_entry_evaluator",
        "evaluate_paper_trade_entry",
    ),
    "evaluate_open_paper_trade_position": (
        "services.paper_trading.paper_trade_position_evaluator",
        "evaluate_open_paper_trade_position",
    ),
    "PaperTradingEngineAdapterV1": (
        "services.paper_trading.paper_trading_engine_adapter_v1",
        "PaperTradingEngineAdapterV1",
    ),
    "PaperTradingEngineAdapterInputV1": (
        "services.paper_trading.paper_trading_engine_adapter_v1",
        "PaperTradingEngineAdapterInputV1",
    ),
    "PaperTradingEngineAdapterResultV1": (
        "services.paper_trading.paper_trading_engine_adapter_v1",
        "PaperTradingEngineAdapterResultV1",
    ),
    "PaperTradePersistenceService": (
        "services.paper_trading.paper_trade_persistence_service",
        "PaperTradePersistenceService",
    ),
    "PaperTradeRecoveryService": (
        "services.paper_trading.paper_trade_recovery_service",
        "PaperTradeRecoveryService",
    ),
    "PaperTradeReplayCoordinator": (
        "services.paper_trading.paper_trade_replay_coordinator",
        "PaperTradeReplayCoordinator",
    ),
}


__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    export = _EXPORTS.get(name)

    if export is None:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )

    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)

    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))