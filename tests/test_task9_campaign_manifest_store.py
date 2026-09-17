from tests.test_task9_campaign_manifest_v1 import _manifest
from services.certification.task9_campaign_manifest_store import Task9CampaignManifestStore
import pytest
def test_manifest_store_roundtrip_conflict_corruption(tmp_path):
 s=Task9CampaignManifestStore(tmp_path);m=_manifest();s.save(m);assert Task9CampaignManifestStore(tmp_path).get(m.campaign_id)==m
 with pytest.raises(ValueError):s.save(_manifest(campaign_version="2"))
 (tmp_path/"campaigns"/"bad.json").write_text("{")
 with pytest.raises(ValueError):s.get("bad")
