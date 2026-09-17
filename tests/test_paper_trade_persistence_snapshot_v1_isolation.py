def test_snapshot_uses_json_not_pickle():
 from pathlib import Path
 text=Path('services/contracts/paper_trade_persistence_snapshot_v1.py').read_text(encoding='utf8')
 assert 'pickle' not in text and 'json' in text
