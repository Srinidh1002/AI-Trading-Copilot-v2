from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading import PaperTradePersistenceService,PaperTradeRecoveryService
from tests.test_paper_trade_persistence_snapshot_v1 import make_snapshot
def test_recovery_is_repeatable_and_fails_closed_on_corruption(tmp_path):
 repository=PaperTradeRepository(tmp_path/'typed.json');service=PaperTradePersistenceService(repository);service.save(make_snapshot());recovery=PaperTradeRecoveryService(service)
 assert recovery.recover()==recovery.recover()
 raw=repository.get_trade('typed-trade');raw['typed_p7_integrity_hash']='wrong';repository.save_trade(raw)
 import pytest
 with pytest.raises(ValueError):recovery.recover()
