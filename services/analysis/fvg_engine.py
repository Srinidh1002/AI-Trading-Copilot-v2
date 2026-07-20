"""
Fair Value Gap Engine V1
"""


def detect_fvg(df):

    bullish = []
    bearish = []

    data = df.reset_index(drop=True)

    for i in range(2, len(data)):

        c1 = data.iloc[i - 2]
        c2 = data.iloc[i - 1]
        c3 = data.iloc[i]

        # Bullish FVG
        if c1["high"] < c3["low"]:

            bullish.append({

                "top": float(c3["low"]),

                "bottom": float(c1["high"]),

                "time": str(c2["timestamp"]),
            })

        # Bearish FVG
        elif c1["low"] > c3["high"]:

            bearish.append({

                "top": float(c1["low"]),

                "bottom": float(c3["high"]),

                "time": str(c2["timestamp"]),
            })

    return {

        "bullish": bullish[-1] if bullish else None,

        "bearish": bearish[-1] if bearish else None,
    }