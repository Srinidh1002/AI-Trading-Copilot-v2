def test_typed_evaluators_do_not_import_legacy_engine():
 from pathlib import Path
 for name in ('paper_trade_entry_evaluator.py','paper_trade_position_evaluator.py'):
  assert 'paper_trading_engine' not in Path('services/paper_trading',name).read_text(encoding='utf8')
