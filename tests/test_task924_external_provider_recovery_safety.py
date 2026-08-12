from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from services.certification.task9_external_provider_recovery_probe import bootstrap_verified_blocker, run_recovery_probe


IST=ZoneInfo("Asia/Kolkata"); NOW=datetime(2026,8,10,13,5,tzinfo=IST)
class Gate:
 def acquire(self): return None
class Cooldown:
 def active(self): return None
class Client:
 broker_order_submission=False; live_execution_eligible=False
 def __init__(self):self.order_calls=0
 def get_historical_data(self,**_):return {"status":True,"data":[["2026-08-10T12:55:00+05:30",100,101,99,100,10]]}

def test_bootstrap_and_recovery_have_no_task9_counting_or_order_side_effects(tmp_path):
 bootstrap_verified_blocker(persistence_root=tmp_path,official_run_id="run",observed_at=NOW-timedelta(hours=2))
 client=Client(); result=run_recovery_probe(persistence_root=tmp_path,official_run_id="run",now=NOW,client=client,gate=Gate(),cooldown=Cooldown())
 assert result["status"]=="CLEARED" and client.broker_order_submission is False and client.live_execution_eligible is False
 assert not list(tmp_path.glob("task9-cycle-results/*"))
 assert not any(path.name in {"prediction-ledger.json","progress.json","reconciliation.json"} for path in tmp_path.rglob("*"))
