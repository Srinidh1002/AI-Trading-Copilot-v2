from __future__ import annotations
from dataclasses import dataclass
from datetime import date,datetime
from services.contracts.task9_run_classification_v1 import validate_task9_run_classification
from services.contracts.task9_campaign_manifest_v1 import Task9CampaignStatus
@dataclass(frozen=True,slots=True)
class Task9CampaignRunContributionV1:
 market_date:date;official_run_id:str;run_classification:str;nifty_countable_contribution:int;sensex_countable_contribution:int;wait_completed_count:int=0;no_trade_completed_count:int=0;unavailable_count:int=0;invalid_count:int=0;excluded_count:int=0;open_or_pending_count:int=0;reconciliation_pending_count:int=0;source_refs:tuple[str,...]=()
 def __post_init__(self):
  if type(self.market_date)is not date or not isinstance(self.official_run_id,str) or not self.official_run_id.strip():raise ValueError("run identity")
  object.__setattr__(self,"run_classification",validate_task9_run_classification(self.run_classification))
  for n in self.__dataclass_fields__:
   if n.endswith("contribution") or n.endswith("count") or n in {"unavailable_count","invalid_count","excluded_count","open_or_pending_count","reconciliation_pending_count"}:
    if type(getattr(self,n))is not int or getattr(self,n)<0:raise ValueError(n)
  if self.run_classification!="OFFICIAL_CERTIFICATION" and (self.nifty_countable_contribution or self.sensex_countable_contribution):raise ValueError("non-official contribution")
@dataclass(frozen=True,slots=True)
class Task9CampaignIndexV1:
 campaign_id:str;campaign_manifest_ref:str;campaign_status:Task9CampaignStatus;updated_at:datetime;market_day_entries:tuple[Task9CampaignRunContributionV1,...];nifty_countable_total:int;sensex_countable_total:int;nifty_target:int=100;sensex_target:int=100;schema_version:str="task9_campaign_index.v1"
 def __post_init__(self):
  if not self.campaign_id or not self.campaign_manifest_ref or self.schema_version!="task9_campaign_index.v1":raise ValueError("index identity")
  object.__setattr__(self,"campaign_status",Task9CampaignStatus(self.campaign_status))
  if not isinstance(self.market_day_entries,tuple) or any(type(x)is not Task9CampaignRunContributionV1 for x in self.market_day_entries):raise ValueError("entries")
  ids=[x.official_run_id for x in self.market_day_entries]
  if len(ids)!=len(set(ids)):raise ValueError("duplicate run")
  a=sum(x.nifty_countable_contribution for x in self.market_day_entries if x.run_classification=="OFFICIAL_CERTIFICATION");b=sum(x.sensex_countable_contribution for x in self.market_day_entries if x.run_classification=="OFFICIAL_CERTIFICATION")
  if (self.nifty_countable_total,self.sensex_countable_total)!=(a,b) or self.nifty_target!=100 or self.sensex_target!=100:raise ValueError("totals")
 @property
 def numeric_target_met(self):return self.nifty_countable_total>=100 and self.sensex_countable_total>=100
 def to_dict(self):return {"schema_version":self.schema_version,"campaign_id":self.campaign_id,"campaign_manifest_ref":self.campaign_manifest_ref,"campaign_status":self.campaign_status.value,"updated_at":self.updated_at.isoformat(),"nifty_countable_total":self.nifty_countable_total,"sensex_countable_total":self.sensex_countable_total,"nifty_target":100,"sensex_target":100,"market_day_entries":[{n:(getattr(x,n).isoformat() if n=="market_date" else list(getattr(x,n)) if n=="source_refs" else getattr(x,n)) for n in x.__dataclass_fields__} for x in self.market_day_entries]}
 @classmethod
 def from_dict(cls,d):
  try:
   rows=[]
   for x in d["market_day_entries"]:
    x=dict(x);x["market_date"]=date.fromisoformat(x["market_date"]);x["source_refs"]=tuple(x["source_refs"]);rows.append(Task9CampaignRunContributionV1(**x))
   return cls(d["campaign_id"],d["campaign_manifest_ref"],d["campaign_status"],datetime.fromisoformat(d["updated_at"]),tuple(rows),d["nifty_countable_total"],d["sensex_countable_total"],d.get("nifty_target",100),d.get("sensex_target",100),d.get("schema_version","task9_campaign_index.v1"))
  except (KeyError,TypeError,ValueError) as e:raise ValueError("index serialization") from e
