import subprocess,sys
def test_public_p6_import_subprocess():
 code='from services.trade_planning import integrate_three_target_trade_plan,plan_capital_quantity;print("OK")'
 r=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True);assert r.returncode==0 and r.stdout.strip()=='OK'
