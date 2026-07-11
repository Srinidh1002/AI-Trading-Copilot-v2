from services.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
)

from services.live_readiness_checker import (
    check_live_readiness,
)


EXCHANGE = "NSE"
NIFTY_TOKEN = "99926000"


print("Fetching live NIFTY multi-timeframe data...")

service = LiveMultiTimeframeData()

timeframes = service.fetch_all(
    exchange=EXCHANGE,
    symboltoken=NIFTY_TOKEN,
)

print("\nCANDLES RECEIVED")
print("================")

for timeframe, data in timeframes.items():
    print(
        f"{timeframe}: {len(data)} candles"
    )


readiness = check_live_readiness(
    timeframes
)

print("\nREADINESS RESULT")
print("================")

print(
    "Ready:",
    readiness["ready"],
)

for timeframe, result in (
    readiness["checks"].items()
):
    print(
        timeframe,
        "->",
        result,
    )

if readiness["reasons"]:
    print("\nISSUES")

    for reason in readiness["reasons"]:
        print("-", reason)