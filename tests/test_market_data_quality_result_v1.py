from datetime import datetime,timezone
import pytest
from services.contracts import MarketDataQualityResultV1
NOW=datetime(2025,1,1,tzinfo=timezone.utc)
@pytest.mark.parametrize("n",range(50))
def test_quality(n):assert MarketDataQualityResultV1("r",NOW,"QUOTE","VALID",item_count=1,valid_item_count=1).quality_status=="VALID"
