"""
Trade Executor V2
"""


def execute_trade(decision):

    if decision["confidence"] < 75:
        return {
            "status": "NO TRADE",
            "reason": "Low Confidence",
        }

    return {
        "status": "READY",
        "action": decision["trend"]["trend"],
        "entry": decision["risk"]["ENTRY"],
        "stop_loss": decision["risk"]["STOP_LOSS"],
        "target1": decision["risk"]["TARGET1"],
        "target2": decision["risk"]["TARGET2"],
    }