import json
from pathlib import Path
from services.certification.task9_atomic_file_replace import replace_task9_atomic_file
from services.contracts.task9_campaign_manifest_v1 import Task9CampaignManifestV1
class Task9CampaignManifestStore:
 def __init__(self,root):self.root=Path(root)
 def _p(self,id):return self.root/"campaigns"/f"{id}.json"
 def save(self,x):
  p=self._p(x.campaign_id);p.parent.mkdir(parents=True,exist_ok=True)
  if p.exists():
   if self.get(x.campaign_id)!=x:raise ValueError("conflicting campaign manifest")
   return x
  t=p.with_name(p.name+".tmp");t.write_text(json.dumps(x.to_dict(),sort_keys=True),encoding="utf8");replace_task9_atomic_file(t,p);return x
 def get(self,id):
  p=self._p(id)
  if not p.exists():return None
  try:return Task9CampaignManifestV1.from_dict(json.loads(p.read_text(encoding="utf8")))
  except Exception as e:raise ValueError("invalid campaign manifest") from e
