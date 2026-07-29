import subprocess,sys
from pathlib import Path
def test_pure_import():
 s=(Path(__file__).parents[1]/'services/trade_planning/option_contract_selector.py').read_text().lower();assert not any(x in s for x in ('provider','broker','execution','order manager','portfolio','database','dashboard','streamlit','random','uuid','datetime.now','date.today','pandas','numpy','scipy','place_order','submit_order','execute_order','cancel_order','slippage','brokerage','tax','gst','stt','expiry_date -','spot'))
 r=subprocess.run([sys.executable,'-c','from services.trade_planning import select_option_contract;print("OK")'],capture_output=True,text=True);assert r.stdout.strip()=='OK'
