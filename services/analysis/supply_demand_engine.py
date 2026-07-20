"""
Supply Demand Engine V1
"""


def detect_supply_demand(swings):

    supply = None
    demand = None

    if swings["last_swing_high"]:

        supply = {

            "price": swings["last_swing_high"]

        }

    if swings["last_swing_low"]:

        demand = {

            "price": swings["last_swing_low"]

        }

    return {

        "supply": supply,

        "demand": demand,
    }