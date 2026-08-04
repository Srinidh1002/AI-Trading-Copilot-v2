from datetime import datetime,timezone
from services.contracts import ThreeTargetEvaluationInputV1
def _i(**x):
 d=dict(evaluation_id='e',evaluation_result_id='r',evaluated_at=datetime(2026,1,1,tzinfo=timezone.utc),trade_plan_input_id='p',policy_id='P',entry_evaluation_result_id='er',stop_evaluation_result_id='sr',underlying_symbol='NIFTY',exchange='NSE',direction='BULLISH',option_right='CALL',entry_reference_price=100.,stop_loss_price=90.,stop_distance=10.,stop_distance_fraction=.1,atr_value=10.,expected_move_value=10.,structure_target_1=110.,structure_target_2=120.,structure_target_3=130.);d.update(x);return ThreeTargetEvaluationInputV1(**d)
def test_valid():assert _i().to_json()==_i().to_json()
