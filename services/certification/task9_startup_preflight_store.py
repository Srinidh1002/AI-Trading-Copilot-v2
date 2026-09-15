from __future__ import annotations
import json
from pathlib import Path
from services.certification.task9_atomic_file_replace import replace_task9_atomic_file
from services.contracts.task9_startup_preflight_v1 import Task9StartupPreflightResultV1
class Task9StartupPreflightStore:
 def __init__(self,root):self.root=Path(root)
 def _path(self,preflight_id):
  if type(preflight_id)is not str or not preflight_id.strip() or "/" in preflight_id or "\\" in preflight_id:raise ValueError("preflight_id")
  return self.root/"startup-preflights"/f"{preflight_id}.json"
 def save(self,result):
  if type(result)is not Task9StartupPreflightResultV1:raise TypeError("result")
  p=self._path(result.preflight_id)
  if p.exists():
   old=self.get(result.preflight_id)
   if old!=result:raise ValueError("conflicting preflight receipt")
   return old
  p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+".tmp")
  try:tmp.write_text(json.dumps(result.to_dict(),sort_keys=True,separators=(",",":")),encoding="utf-8");replace_task9_atomic_file(tmp,p)
  finally:tmp.unlink(missing_ok=True)
  return result
 def get(self,preflight_id):
  p=self._path(preflight_id)
  if not p.exists():return None
  try:return Task9StartupPreflightResultV1.from_dict(json.loads(p.read_text(encoding="utf-8")))
  except (OSError,ValueError,json.JSONDecodeError) as e:raise ValueError("invalid preflight receipt") from e
