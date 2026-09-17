import subprocess,sys
from pathlib import Path
def test_pure_import():
 s=(Path(__file__).parents[1]/'services/contracts/capital_quantity_planning_policy_v1.py').read_text().lower();assert not any(x in s for x in ('provider','broker','place_order','submit_order','portfolio','database','streamlit','network','pandas','numpy','scipy','random','uuid','datetime.now','date.today','quantity calculation'))
 r=subprocess.run([sys.executable,'-c','from services.contracts import CapitalQuantityPlanningPolicyV1;print("OK")'],capture_output=True,text=True);assert r.stdout.strip()=='OK'
