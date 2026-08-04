from datetime import datetime,timezone
import pytest
from test_paper_execution_replay import canonical,observations,NOW
from services.paper import replay_canonical_paper_execution,build_paper_execution_observations
@pytest.mark.parametrize("repeat",range(40))
def test_replay_and_builder_are_read_only(repeat):
 c=canonical();before=c.to_json();replay_canonical_paper_execution(canonical_execution_result=c,observations=observations(c),clock=lambda:NOW);assert c.to_json()==before
