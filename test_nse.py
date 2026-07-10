from services.nse_option_chain import get_nifty_option_chain

data = get_nifty_option_chain()

print(type(data))

print(data)