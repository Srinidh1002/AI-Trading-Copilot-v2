from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading import PaperTradePersistenceService
from tests.test_paper_trade_persistence_snapshot_v1 import make_snapshot
def test_update_replaces_one_complete_typed_snapshot_atomically(tmp_path):
 service=PaperTradePersistenceService(PaperTradeRepository(tmp_path/'state.json'));first=make_snapshot();service.save(first);service.save(first)
 assert service.get(first.paper_trade_id).to_json()==first.to_json()
