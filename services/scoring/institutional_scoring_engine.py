"""
Institutional Scoring Engine

Calculates the final institutional trade quality score.
"""


class InstitutionalScoringEngine:

    def calculate(
        self,
        snapshot,
        decision,
    ):

        option = snapshot.get(
            "option_analysis",
            {},
        )

        score = 0

        reasons = []

        # --------------------------------------------------
        # Trend
        # --------------------------------------------------

        trend = decision.get(
            "trend",
            {},
        )

        if trend.get("strength") == "Very Strong":

            score += 15

            reasons.append(
                "Very Strong Trend"
            )

        elif trend.get("strength") == "Strong":

            score += 12

            reasons.append(
                "Strong Trend"
            )

        elif trend.get("strength") == "Moderate":

            score += 8

        # --------------------------------------------------
        # PCR
        # --------------------------------------------------

        pcr = option.get(
            "PCR",
            {},
        )

        if pcr.get("Bias") == "Strong Bullish":

            score += 12

            reasons.append(
                "Strong Bullish PCR"
            )

        elif pcr.get("Bias") == "Bullish":

            score += 8

        elif pcr.get("Bias") == "Strong Bearish":

            score += 12

            reasons.append(
                "Strong Bearish PCR"
            )

        elif pcr.get("Bias") == "Bearish":

            score += 8

        # --------------------------------------------------
        # OI
        # --------------------------------------------------

        oi = option.get(
            "OI",
            {},
        )

        if oi.get("Bias"):

            score += 10

            reasons.append(
                "OI Confirmation"
            )

        # --------------------------------------------------
        # Option Flow
        # --------------------------------------------------

        flow = option.get(
            "Flow",
            {},
        )

        if flow.get("Bias") == "Strong Bullish":

            score += 15

            reasons.append(
                "Institutional Put Writing"
            )

        elif flow.get("Bias") == "Strong Bearish":

            score += 15

            reasons.append(
                "Institutional Call Writing"
            )

        elif flow.get("Bias") in (
            "Bullish",
            "Bearish",
        ):

            score += 10

        # --------------------------------------------------
        # OI Change
        # --------------------------------------------------

        oi_change = option.get(
            "OIChange",
            {},
        )

        summary = oi_change.get(
            "Summary",
            {},
        )

        score += min(

            summary.get(
                "BullScore",
                0,
            )

            +

            summary.get(
                "BearScore",
                0,
            ),

            15,

        )

        # --------------------------------------------------
        # Greeks
        # --------------------------------------------------

        greeks = option.get(
            "Greeks",
            {},
        )

        summary = greeks.get(
            "Summary",
            {},
        )

        if summary.get("Bias") != "Neutral":

            score += 10

            reasons.append(
                "Greeks Confirmation"
            )

        iv = summary.get(
            "AverageIV",
            0,
        )

        if iv > 20:

            score += 5

        # --------------------------------------------------
        # Smart Money
        # --------------------------------------------------

        confidence = decision.get(
            "confidence",
            0,
        )

        score += confidence * 0.2

        score = round(
            min(
                score,
                100,
            ),
            2,
        )

        # --------------------------------------------------
        # Grade
        # --------------------------------------------------

        if score >= 90:

            grade = "A+"

        elif score >= 80:

            grade = "A"

        elif score >= 70:

            grade = "B+"

        elif score >= 60:

            grade = "B"

        elif score >= 50:

            grade = "C"

        else:

            grade = "Avoid"

        return {

            "Score": score,

            "Grade": grade,

            "Reasons": reasons,

        }