from services.market.instrument_registry import InstrumentMaster

m = InstrumentMaster()

m.load()

print(m.underlyings()[:10])

print()

print(m.expiries("NIFTY"))