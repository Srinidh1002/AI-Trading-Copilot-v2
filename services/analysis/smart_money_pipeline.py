"""
Smart Money Pipeline

Collects all Smart Money Concept (SMC) analysis
into one unified object.

Every Smart Money detector should be called here.

Author: Saaura AI Trading Copilot
"""

from services.analysis.order_block_engine import (
    detect_order_blocks,
)

from services.analysis.fvg_engine import (
    detect_fvg,
)

# Future Imports
# from services.analysis.supply_demand_engine import detect_supply_demand
# from services.analysis.bos_engine import detect_bos
# from services.analysis.choch_engine import detect_choch


def analyze(df):
    """
    Run every Smart Money detector.

    Returns
    -------
    dict
    """

    result = {}

    # ------------------------------------
    # Order Blocks
    # ------------------------------------

    try:
        result["order_blocks"] = detect_order_blocks(df)

    except Exception as e:
        result["order_blocks"] = {
            "error": str(e)
        }

    # ------------------------------------
    # Fair Value Gaps
    # ------------------------------------

    try:
        result["fair_value_gaps"] = detect_fvg(df)

    except Exception as e:
        result["fair_value_gaps"] = {
            "error": str(e)
        }

    # ------------------------------------
    # Future Modules
    # ------------------------------------

    result["supply_demand"] = None

    result["bos"] = None

    result["choch"] = None

    return result