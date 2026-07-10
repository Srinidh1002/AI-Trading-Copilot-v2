"""
Option AI Service
Analyzes option chain data and converts it into bull/bear scores.
"""

from services.option_chain import get_option_chain


def option_score(symbol="NIFTY"):
    data = get_option_chain(symbol)

    pcr = data["PCR"]

    bull = 0
    bear = 0

    # PCR Analysis
    if pcr > 1:
        bull += 15
    elif pcr < 0.8:
        bear += 15
    else:
        bull += 8
        bear += 8

    return {
        "bull": bull,
        "bear": bear,
        "PCR": pcr,
        "support": data["support"],
        "resistance": data["resistance"],
        "max_pain": data["max_pain"],
    }