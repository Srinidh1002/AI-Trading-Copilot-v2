"""Pure external-context evaluators; no providers or runtime composition."""
from importlib import import_module
__all__ = ("evaluate_global_market_context", "evaluate_institutional_flow_context", "evaluate_event_risk_context", "evaluate_external_market_context", "evaluate_external_context_pipeline")
def __getattr__(name: str):
    if name == "evaluate_global_market_context":
        value = import_module(f"{__name__}.global").evaluate_global_market_context
        globals()[name] = value
        return value
    if name == "evaluate_institutional_flow_context":
        value = import_module(f"{__name__}.institutional").evaluate_institutional_flow_context
        globals()[name] = value
        return value
    if name == "evaluate_event_risk_context":
        value = import_module(f"{__name__}.events").evaluate_event_risk_context
        globals()[name] = value
        return value
    if name == "evaluate_external_market_context":
        value = import_module(f"{__name__}.aggregate").evaluate_external_market_context
        globals()[name] = value
        return value
    if name == "evaluate_external_context_pipeline":
        value = import_module(f"{__name__}.integration").evaluate_external_context_pipeline
        globals()[name] = value
        return value
    raise AttributeError(name)
