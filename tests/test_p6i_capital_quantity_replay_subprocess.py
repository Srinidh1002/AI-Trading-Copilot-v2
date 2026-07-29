import subprocess,sys
def test_fresh_subprocess_import_is_clean():
 code='from services.trade_planning import plan_capital_quantity,resolve_capital_quantity_planning_constraints;print("OK")'
 r=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True);assert r.returncode==0 and r.stdout.strip()=='OK'
