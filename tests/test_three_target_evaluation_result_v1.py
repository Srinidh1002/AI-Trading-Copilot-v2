from tests.test_three_target_evaluation_input_v1 import _i
def test_input_serialization():assert set(_i().to_dict())-set(_i().semantic_dict())=={'evaluation_id','evaluation_result_id','evaluated_at','source_timestamps'}
