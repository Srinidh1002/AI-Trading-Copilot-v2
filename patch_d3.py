"""D3 — Add certification_eligible to trade records + propagate through ledger.

At entry:  compute certification_eligible from safety + market + book + lot
Ledger:    whitelist the field + companion flags (execution_mode,
           broker_submission, live_execution) into outcome record

Note: certification_eligible at ENTRY means "eligible to be counted IF it
closes terminal+reconciled+unique". Final countability is decided downstream.
"""
path_bot = "src/target_focused_bot.py"
with open(path_bot, encoding="utf-8") as f:
    bot = f.read()

if "D3_cert_eligible" in bot:
    print("D3 already applied to bot")
else:
    # 1. Add certification_eligible + companions to active_trade dict at entry
    old_dict = """            'sl_price': sl_price,
            'reason': trade['reason'],
            'status': 'OPEN'
        }"""
    new_dict = """            'sl_price': sl_price,
            'reason': trade['reason'],
            'status': 'OPEN',
            # D3_cert_eligible — entry-time certification contract
            'execution_mode': self.EXECUTION_MODE,
            'broker_submission': self.BROKER_SUBMISSION,
            'live_execution': self.LIVE_EXECUTION,
            'certification_eligible': (
                self.EXECUTION_MODE == "PAPER"
                and self.BROKER_SUBMISSION is False
                and self.LIVE_EXECUTION is False
                and self.market in ("NIFTY", "SENSEX")
                and _bid > 0 and _ask > 0 and _ask > _bid
                and self.lot_size > 0
            ),
        }"""
    if old_dict not in bot:
        raise SystemExit("D3 active_trade anchor not found")
    bot = bot.replace(old_dict, new_dict, 1)
    with open(path_bot, "w", encoding="utf-8") as f:
        f.write(bot)
    print("D3: certification_eligible added to active_trade dict")

# 2. Whitelist those fields in outcome_ledger.py
path_ledger = "src/outcome_ledger.py"
with open(path_ledger, encoding="utf-8") as f:
    ledger = f.read()

if "D3_cert_eligible" in ledger:
    print("D3 already applied to ledger")
else:
    old_rec = '''            "rank_score": trade.get("rank_score"),
        }'''
    new_rec = '''            "rank_score": trade.get("rank_score"),
            # D3_cert_eligible — certification contract fields
            "execution_mode": trade.get("execution_mode"),
            "broker_submission": trade.get("broker_submission"),
            "live_execution": trade.get("live_execution"),
            "certification_eligible": trade.get("certification_eligible"),
        }'''
    if old_rec not in ledger:
        raise SystemExit("D3 ledger anchor not found")
    ledger = ledger.replace(old_rec, new_rec, 1)
    with open(path_ledger, "w", encoding="utf-8") as f:
        f.write(ledger)
    print("D3: certification_eligible whitelisted in outcome_ledger")
