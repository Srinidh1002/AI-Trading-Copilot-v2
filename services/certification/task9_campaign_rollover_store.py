"""Atomic, restart-safe receipt persistence for campaign rollover."""
from __future__ import annotations
import json
from dataclasses import replace
from pathlib import Path
from services.certification.task9_atomic_file_replace import replace_task9_atomic_file
from services.contracts.task9_campaign_rollover_v1 import Task9CampaignRolloverReceiptStatus,Task9CampaignRolloverReceiptV1
_ORDER={Task9CampaignRolloverReceiptStatus.PLANNED:0,Task9CampaignRolloverReceiptStatus.RUN_MANIFEST_PERSISTED:1,Task9CampaignRolloverReceiptStatus.POINTER_UPDATED:2,Task9CampaignRolloverReceiptStatus.APPLIED:3}
class Task9CampaignRolloverStore:
 def __init__(self,root): self.root=Path(root)
 def _path(self,id): return self.root/"campaign-rollovers"/f"{id}.json"
 def get(self,id):
  p=self._path(id)
  if not p.exists(): return None
  try: r=Task9CampaignRolloverReceiptV1.from_dict(json.loads(p.read_text(encoding="utf-8")))
  except Exception as exc: raise ValueError("invalid campaign rollover receipt") from exc
  if r.rollover_id!=id: raise ValueError("rollover receipt identity mismatch")
  return r
 read=get
 def _write(self,r):
  p=self._path(r.rollover_id); p.parent.mkdir(parents=True,exist_ok=True); t=p.with_name(p.name+".tmp")
  try: t.write_text(json.dumps(r.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False),encoding="utf-8"); replace_task9_atomic_file(t,p)
  finally: t.unlink(missing_ok=True)
  return r
 def save(self,r):
  if type(r) is not Task9CampaignRolloverReceiptV1: raise TypeError("receipt")
  old=self.get(r.rollover_id)
  if old is None: return self._write(r)
  if old.immutable_identity()!=r.immutable_identity(): raise ValueError("conflicting campaign rollover receipt")
  if _ORDER[r.status]<_ORDER[old.status]: raise ValueError("rollover receipt status regression")
  if _ORDER[r.status]>_ORDER[old.status]+1: raise ValueError("rollover receipt status skip")
  return old if r.status==old.status else self._write(r)
 def advance(self,id,status,*,applied_at):
  old=self.get(id)
  if old is None: raise ValueError("missing campaign rollover receipt")
  return self.save(replace(old,status=Task9CampaignRolloverReceiptStatus(status),applied_at=applied_at))
