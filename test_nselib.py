from nselib import derivatives

data = derivatives.nse_live_option_chain("NIFTY")

print(data)