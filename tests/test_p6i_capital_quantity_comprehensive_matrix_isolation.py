def test_pure_matrix_import():
 from services.trade_planning.capital_quantity_planner import _allocate_target_lots
 assert _allocate_target_lots(1,(1,1,1))[0]==(1,0,0)
