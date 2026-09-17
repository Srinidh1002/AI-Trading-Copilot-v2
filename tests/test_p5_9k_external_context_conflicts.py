from tests.fixtures.external_context import external_observation,institutional_snapshot,run_external_context_replay
def test_global_institutional_conflict_is_preserved():assert run_external_context_replay(observations=(external_observation(),),snapshot=institutional_snapshot(-1),events=()).context_status=="CONFLICTING"
