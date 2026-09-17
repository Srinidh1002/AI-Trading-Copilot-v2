from tests.test_task9_active_campaign_pointer_v1 import _pointer
from tests.test_task9_campaign_manifest_v1 import _manifest
from services.certification.task9_active_campaign_pointer_store import Task9ActiveCampaignPointerStore
import pytest
def test_pointer_transitions_and_manifest_boundary(tmp_path):
 s=Task9ActiveCampaignPointerStore(tmp_path);m=_manifest();s.set(_pointer(),manifest=m);s=Task9ActiveCampaignPointerStore(tmp_path);s.set(_pointer(status="PAUSED"),manifest=m);s.set(_pointer(status="ACTIVE"),manifest=m);s.set(_pointer(status="HALTED"),manifest=m);s.set(_pointer(status="COMPLETED"),manifest=m)
 with pytest.raises(ValueError):s.set(_pointer(status="ACTIVE"),manifest=m)
 with pytest.raises(ValueError):Task9ActiveCampaignPointerStore(tmp_path/"x").set(_pointer(campaign_root="wrong"),manifest=m)
