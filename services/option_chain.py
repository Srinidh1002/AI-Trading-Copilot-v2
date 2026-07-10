"""
Temporary Option Chain Service
Version 1
"""

from random import randint, uniform


def get_option_chain(symbol="NIFTY"):

    pcr = round(uniform(0.8, 1.3), 2)

    support = randint(24800, 25200)

    resistance = support + 200

    max_pain = support + 100

    call_oi = randint(2_000_000, 8_000_000)

    put_oi = int(call_oi * pcr)

    return {
        "PCR": pcr,
        "call_oi": call_oi,
        "put_oi": put_oi,
        "support": support,
        "resistance": resistance,
        "max_pain": max_pain,
    }