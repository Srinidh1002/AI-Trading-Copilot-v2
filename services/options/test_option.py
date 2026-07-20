from services.options.angel_option_client import AngelOptionClient

client = AngelOptionClient()

print(
    client.get_option_greeks(
        "NIFTY",
        "30JUL2026",
    )
)