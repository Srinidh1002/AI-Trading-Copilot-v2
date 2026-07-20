from services.market.instrument_registry import InstrumentMaster

m = InstrumentMaster()

m.load()

print("\nUnderlyings")
print(m.underlyings()[:10])

expiry = m.nearest_expiry("NIFTY")

print("\nNearest Expiry")
print(expiry)

chain = m.option_chain(
    "NIFTY",
    expiry,
)

print("\nCalls :", len(chain["CE"]))
print("Puts  :", len(chain["PE"]))

atm = m.atm_strike(
    "NIFTY",
    expiry,
    24346.7,
)

print("\nATM Strike")
print(atm)

print("\nFirst Call")
print(chain["CE"][0])

print("\nFirst Put")
print(chain["PE"][0])