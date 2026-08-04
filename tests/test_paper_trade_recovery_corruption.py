import pytest
from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading import PaperTradePersistenceService,PaperTradeRecoveryService
from tests.test_paper_trade_persistence_snapshot_v1 import make_snapshot
def test_corrupt_snapshot_is_rejected_without_recovery(tmp_path):
 repo=PaperTradeRepository(tmp_path/'state.json');service=PaperTradePersistenceService(repo);service.save(make_snapshot());raw=repo.get_trade('typed-trade');del raw['typed_p7_snapshot']['position'];repo.save_trade(raw)
 with pytest.raises(ValueError):PaperTradeRecoveryService(service).recover()
