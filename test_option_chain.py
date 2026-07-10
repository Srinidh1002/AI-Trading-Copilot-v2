from services.option_chain_live import get_option_chain

data = get_option_chain("NIFTY")

print(type(data))

print(data.keys())
