from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading import PaperTradePersistenceService
from tests.test_paper_trade_persistence_snapshot_v1 import make_snapshot
def test_service_saves_fetches_and_lists_active_snapshots(tmp_path):
 service=PaperTradePersistenceService(PaperTradeRepository(tmp_path/'typed.json'));saved=service.save(make_snapshot())
 assert service.get('typed-trade').to_json()==saved.to_json() and service.get_by_idempotency_key('key-1')==saved and service.list_active()==(saved,)

def test_service_lists_real_snapshots_in_canonical_created_order(tmp_path):
 from dataclasses import replace
 service=PaperTradePersistenceService(PaperTradeRepository(tmp_path/'typed.json'));late=replace(make_snapshot(),paper_trade_id='z-trade',adapter_idempotency_key='z-key');early=replace(make_snapshot(),paper_trade_id='a-trade',adapter_idempotency_key='a-key')
 service.save(late);service.save(early)
 assert [snapshot.paper_trade_id for snapshot in service.list_all()]==['a-trade','z-trade']
