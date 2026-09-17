from tests.test_task9_campaign_manifest_v1 import _manifest
from tests.test_task9_active_campaign_pointer_v1 import _pointer
from services.certification.task9_campaign_authority import validate_task9_campaign_pointer_compatibility
import pytest
def test_compatible_and_mismatch():
 assert validate_task9_campaign_pointer_compatibility(_manifest(),_pointer())
 with pytest.raises(ValueError):validate_task9_campaign_pointer_compatibility(_manifest(),_pointer(campaign_id="other"))
