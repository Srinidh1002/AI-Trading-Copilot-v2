import json
from pathlib import Path
from services.certification.task9_atomic_file_replace import replace_task9_atomic_file
from services.contracts.task9_campaign_manifest_v1 import Task9ActiveCampaignPointerV1,Task9ActiveCampaignPointerStatus
class Task9ActiveCampaignPointerStore:
 def __init__(self,root):self.path=Path(root)/"active-campaign.json"
 def get(self):
  if not self.path.exists():return None
  try:return Task9ActiveCampaignPointerV1.from_dict(json.loads(self.path.read_text(encoding="utf8")))
  except Exception as e:raise ValueError("invalid active campaign pointer") from e
 def set(
  self,
  x,
  *,
  manifest=None,
  require_runtime_config_provenance_match=True,
 ):
  if type(require_runtime_config_provenance_match) is not bool:
   raise TypeError("require_runtime_config_provenance_match")
  if manifest is not None:
   from services.certification.task9_campaign_authority import validate_task9_campaign_pointer_compatibility
   validate_task9_campaign_pointer_compatibility(
    manifest,
    x,
    require_runtime_config_provenance_match=(
     require_runtime_config_provenance_match
    ),
   )
  old=self.get()
  if old and old.campaign_id!=x.campaign_id:raise ValueError("pointer campaign mismatch")
  allowed={"ACTIVE":{"ACTIVE","PAUSED","HALTED","COMPLETED"},"PAUSED":{"PAUSED","ACTIVE","HALTED","COMPLETED"},"HALTED":{"HALTED","COMPLETED"},"COMPLETED":{"COMPLETED"}}
  if old and x.status.value not in allowed[old.status.value]:raise ValueError("invalid pointer transition")
  self.path.parent.mkdir(parents=True,exist_ok=True);t=self.path.with_name(self.path.name+".tmp");t.write_text(json.dumps(x.to_dict(),sort_keys=True),encoding="utf8");replace_task9_atomic_file(t,self.path);return x
