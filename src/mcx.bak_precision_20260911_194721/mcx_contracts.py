"""MCX contract specifications — PROVISIONAL until MCX-01 doc freeze.
Sources: Blueprint §4/§6.3, MCX circulars [S3][S5][S7].
NO broker calls. Pure data.
"""
PROVISIONAL = True  # flip to False after MCX-01 sign-off

# Angel master stores MCX strike & tick values x100.
# Verified 2026-09-11: CRUDEOILM17SEP266900CE has strike=690000 -> INR 6900.
ANGEL_MASTER_SCALE = 100


CRUDEOILM = {
    "product": "CRUDEOILM",
    "display_name": "Crude Oil Mini",
    "exchange": "MCX",
    "exch_seg": "MCX",
    "future_instr_type": "FUTCOM",
    "option_instr_type": "OPTFUT",
    "trading_unit": 10,
    "quote_base": "INR_PER_BARREL",
    "cash_multiplier": 10,
    "tick_size": 0.05,
    "strike_interval": 50,
    "option_type": "EUROPEAN",
    "settlement": "OPTIONS_ON_FUTURES",
    "session": {"start": "09:00", "end_default": "23:30", "end_dst_us_summer": "23:55"},
    "provenance": "Blueprint §4.1 / MCX circular [S3]",
    "status": "PROVISIONAL",
}

GOLDM = {
    "product": "GOLDM",
    "display_name": "Gold Mini",
    "exchange": "MCX",
    "exch_seg": "MCX",
    "future_instr_type": "FUTCOM",
    "option_instr_type": "OPTFUT",
    "trading_unit": 100,
    "quote_base": "INR_PER_10G",
    "cash_multiplier": 10,
    "tick_size": 1.0,
    "strike_interval": 100,
    "option_type": "EUROPEAN",
    "settlement": "OPTIONS_ON_FUTURES",
    "session": {"start": "09:00", "end_default": "23:30", "end_dst_us_summer": "23:55"},
    "provenance": "Blueprint §4 / MCX circular [S5]",
    "status": "PROVISIONAL",
}

NATGASMINI = {
    "product": "NATGASMINI",
    "display_name": "Natural Gas Mini",
    "exchange": "MCX",
    "exch_seg": "MCX",
    "future_instr_type": "FUTCOM",
    "option_instr_type": "OPTFUT",
    "trading_unit": 250,
    "quote_base": "INR_PER_MMBTU",
    "cash_multiplier": 250,
    "tick_size": 0.10,
    "strike_interval": 5,
    "option_type": "EUROPEAN",
    "settlement": "OPTIONS_ON_FUTURES",
    "session": {"start": "09:00", "end_default": "23:30", "end_dst_us_summer": "23:55"},
    "provenance": "Blueprint §4 / MCX circular [S7]",
    "status": "PROVISIONAL",
}

PRODUCTS = {
    "CRUDEOILM": CRUDEOILM,
    "GOLDM": GOLDM,
    "NATGASMINI": NATGASMINI,
}
