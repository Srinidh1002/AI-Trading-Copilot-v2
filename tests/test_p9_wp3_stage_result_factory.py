from datetime import datetime,timezone
from services.paper_orchestration.stage_result_factory import build_completed_stage_result,build_failed_stage_result
NOW=datetime(2026,1,8,9,30,tzinfo=timezone.utc)
class Source:
    result_id='source-result-1'
    def to_json(self): return '{"value":1}'
def test_completed_stage_captures_source_identity():
    result=build_completed_stage_result(stage_result_id='cycle-1:data',cycle_id='cycle-1',stage='DATA',started_at=NOW,completed_at=NOW,source_result=Source())
    assert result.status=='COMPLETED' and result.source_result_type=='Source' and result.source_result_id=='source-result-1' and len(result.source_semantic_hash)==64
def test_failed_stage_is_fail_closed():
    result=build_failed_stage_result(stage_result_id='cycle-1:data:failed',cycle_id='cycle-1',stage='DATA',started_at=NOW,completed_at=NOW,failure_code='DATA_AUTHORITY_FAILURE',message='data failed',retryable=True,source_component='DataAuthority',exception=RuntimeError('data failed'))
    assert result.status=='FAILED' and result.failure is not None and result.failure.fail_closed is True and result.errors==('DATA_AUTHORITY_FAILURE',)
