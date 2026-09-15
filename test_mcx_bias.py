import os, sys
_HERE = os.path.dirname(os.path.abspath("src/mcx/mcx_snapshot.py"))
sys.path.insert(0, "src")
os.chdir(".")

from dotenv import load_dotenv
import pyotp
from SmartApi import SmartConnect

from mcx.mcx_identity import MCXIdentityResolver
from mcx.mcx_chain import build_chain
from mcx.mcx_external_context import fetch_context
from mcx.mcx_mtf import compute_mtf, print_mtf
from mcx.mcx_bias import compose, print_bias

load_dotenv()

def login():
    obj = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
    r = obj.generateSession(clientCode=os.getenv("ANGEL_USER_ID"),
                            password=os.getenv("ANGEL_PASSWORD"),
                            totp=pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now())
    return obj if r and r.get("status") else None

obj = login()
print("session OK" if obj else "session FAILED")
if not obj: sys.exit(1)

res = MCXIdentityResolver().resolve_active("CRUDEOILM")
fut_token = str(res["futures"]["token"])
print(f"future token = {fut_token}")

mtf = compute_mtf(obj, fut_token, "MCX")
print_mtf(mtf)

chain = build_chain(obj, "CRUDEOILM", window_steps=10)
ctx = fetch_context("CRUDEOILM")

b = compose(chain, ctx, mtf)
print_bias(b)
