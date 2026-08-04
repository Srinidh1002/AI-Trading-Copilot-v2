import ast,os,subprocess,sys
from pathlib import Path
P=Path(__file__).parents[1];F=P/'services/contracts/stop_loss_evaluation_input_v1.py'
def test_clean_imports_and_clock():
 t=ast.parse(F.read_text());roots={n.module.split('.')[0] for n in ast.walk(t) if isinstance(n,ast.ImportFrom) and n.module};assert roots<={'__future__','dataclasses','datetime','types','typing','services','json','math'};assert 'datetime.now' not in F.read_text()
def test_public_import():
 e=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');r=subprocess.run([sys.executable,'-c','from services.contracts import StopLossEvaluationInputV1;print("OK")'],cwd=P,env=e,capture_output=True,text=True);assert r.stdout.strip()=='OK'
