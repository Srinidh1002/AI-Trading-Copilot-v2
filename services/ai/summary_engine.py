"""
Summary Engine V1
"""


def generate_summary(decision, reasons):

    return {

        "decision": decision["status"],

        "action": decision.get("action", "NONE"),

        "summary": " ".join(reasons),

        "entry": decision.get("entry"),

        "stop_loss": decision.get("stop_loss"),

        "target1": decision.get("target1"),

        "target2": decision.get("target2"),
    }