import pytest
from services.paper import run_canonical_paper_execution
@pytest.mark.parametrize("index",range(35))
def test_pipeline_requires_explicit_canonical_risk(index):
 with pytest.raises(TypeError):run_canonical_paper_execution(canonical_risk_result=None,authorization=None,session_validation=None)
