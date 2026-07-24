"""
Institutional AI Trading Copilot

Project-wide response contracts.

These constants define the official keys exchanged between
engines. Using constants prevents spelling mistakes and keeps
all modules synchronized.
"""

# ==========================================================
# Decision
# ==========================================================

DECISION = "decision"
SIGNAL = "signal"
REASON = "reason"

# ==========================================================
# Confidence
# ==========================================================

CONFIDENCE = "confidence"
GRADE = "grade"
TRADE_QUALITY = "trade_quality"

# ==========================================================
# Scores
# ==========================================================

BULL_SCORE = "bull_score"
BEAR_SCORE = "bear_score"
NEUTRAL_SCORE = "neutral_score"

# ==========================================================
# Master Decision
# ==========================================================

FINAL_DECISION = "final_decision"
APPROVAL_STATUS = "approval_status"
ENTRY_ALLOWED = "entry_allowed"
DECISION_SCORE = "decision_score"
DECISION_SUMMARY = "summary"

# ==========================================================
# Trade Plan
# ==========================================================

ENTRY = "entry"
STOP_LOSS = "stop_loss"

TARGET1 = "target1"
TARGET2 = "target2"
TARGET3 = "target3"

# ==========================================================
# Dashboard
# ==========================================================

TREND = "trend"
PATTERN = "pattern"
SUPPLY_DEMAND = "support_resistance"

# ==========================================================
# Risk
# ==========================================================

RISK = "risk"
RISK_LEVEL = "risk_level"

# ==========================================================
# Raw Objects
# ==========================================================

SNAPSHOT = "snapshot"
DECISION_DATA = "decision_data"
MASTER_DECISION_DATA = "master_decision_data"
TRADE_SCORE_DATA = "trade_score_data"
RISK_DATA = "risk_data"