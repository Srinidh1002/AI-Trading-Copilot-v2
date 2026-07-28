from tests.test_global_market_context_evaluator import observation, run
def test_us_group_is_capped_and_order_independent():
 a=(observation("SP500"),observation("NASDAQ"),observation("DOW_JONES"));assert run(a).semantic_dict()==run(tuple(reversed(a))).semantic_dict()
def test_crude_conflict_is_preserved():assert run((observation("BRENT_CRUDE"),observation("WTI_CRUDE","NEGATIVE"))).context_status=="CONFLICTING"
