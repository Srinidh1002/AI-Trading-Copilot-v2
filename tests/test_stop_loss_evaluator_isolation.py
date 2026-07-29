import ast,os,subprocess,sys
from pathlib import Path
P=Path(__file__).parents[1];F=P/'services/trade_planning/stop_loss_evaluator.py'
def test_evaluator_is_pure_contract_boundary():
 t=ast.parse(F.read_text());roots={n.module.split('.')[0] for n in ast.walk(t) if isinstance(n,ast.ImportFrom) and n.module};assert roots<={'__future__','typing','services'};s=F.read_text();assert not any(x in s for x in ('datetime.now','utcnow','time.time','random','uuid','place_order','provider','broker','streamlit'))
def test_public_import():
 e=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');r=subprocess.run([sys.executable,'-c','from services.trade_planning import evaluate_stop_loss;print("OK")'],cwd=P,env=e,capture_output=True,text=True);assert r.stdout.strip()=='OK'
