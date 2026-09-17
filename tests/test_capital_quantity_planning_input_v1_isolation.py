import subprocess,sys
def test_import():
 r=subprocess.run([sys.executable,'-c','from services.contracts import CapitalQuantityPlanningInputV1;print("OK")'],capture_output=True,text=True);assert r.stdout.strip()=='OK'
