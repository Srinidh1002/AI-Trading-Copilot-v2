import subprocess,sys
def test_import():assert subprocess.run([sys.executable,'-c','from services.contracts import CapitalQuantityPlanningResultV1;print("OK")'],capture_output=True,text=True).stdout.strip()=='OK'
