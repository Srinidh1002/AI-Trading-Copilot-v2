"""
Position Sizing Engine

Institutional position sizing based on
confidence, volatility and account risk.
"""


class PositionSizingEngine:

    @staticmethod
    def calculate(
        capital: float,
        confidence: float,
        atr: float,
        entry: float,
        stoploss: float,
        risk_percent: float = 1.0,
    ):

        capital = max(float(capital), 0.0)
        confidence = max(0.0, min(float(confidence), 100.0))
        atr = max(float(atr), 0.0)
        entry = float(entry)
        stoploss = float(stoploss)

        if capital <= 0 or entry <= 0:

            return {
                "capital": capital,
                "risk_amount": 0,
                "quantity": 0,
                "position_value": 0,
                "recommended_exposure": 0,
                "risk_percent": risk_percent,
            }

        # Maximum amount willing to lose
        risk_amount = capital * (risk_percent / 100)

        stop_distance = abs(entry - stoploss)

        if stop_distance <= 0:
            stop_distance = atr

        if stop_distance <= 0:
            stop_distance = entry * 0.005

        quantity = int(risk_amount / stop_distance)

        if quantity < 1:
            quantity = 1

        # Confidence adjustment
        if confidence >= 90:
            multiplier = 1.50
        elif confidence >= 80:
            multiplier = 1.30
        elif confidence >= 70:
            multiplier = 1.10
        elif confidence >= 60:
            multiplier = 1.00
        elif confidence >= 50:
            multiplier = 0.80
        else:
            multiplier = 0.50

        quantity = max(1, int(quantity * multiplier))

        position_value = quantity * entry

        max_exposure = capital * 0.30

        if position_value > max_exposure:

            quantity = max(
                1,
                int(max_exposure / entry),
            )

            position_value = quantity * entry

        return {

            "capital": round(capital, 2),

            "risk_amount": round(risk_amount, 2),

            "risk_percent": risk_percent,

            "quantity": quantity,

            "entry": round(entry, 2),

            "stoploss": round(stoploss, 2),

            "position_value": round(position_value, 2),

            "recommended_exposure": round(
                (position_value / capital) * 100,
                2,
            ),

            "confidence": confidence,

        }