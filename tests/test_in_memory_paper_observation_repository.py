from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import pytest
from services.contracts import PaperExecutionObservationV1
from services.paper.observation_repository import InMemoryPaperExecutionObservationRepository,DuplicatePaperExecutionObservationError,PaperExecutionObservationRepositoryError
NOW=datetime(2025,1,1,tzinfo=timezone.utc)
def obs(n,**c):
 v=dict(observation_id=f"o{n}",observed_at=NOW,stage="REQUEST",outcome="RECORDED",execution_request_id=f"r{n}",underlying_symbol="NIFTY",exchange="NSE");v.update(c);return PaperExecutionObservationV1(**v)
@pytest.mark.parametrize("n",range(70))
def test_save_lookup_filter_and_snapshot(n):
 repo=InMemoryPaperExecutionObservationRepository();v=obs(n);repo.save(v);assert repo.get(v.observation_id)==v and repo.list_by_identity("NIFTY")== (v,) and isinstance(repo.snapshot(),tuple)
def test_duplicate_and_wrong_type_rejected():
 repo=InMemoryPaperExecutionObservationRepository();repo.save(obs(1))
 with pytest.raises(DuplicatePaperExecutionObservationError):repo.save(obs(1))
 with pytest.raises(PaperExecutionObservationRepositoryError):repo.save("bad")
def test_atomic_many_and_concurrent_saves():
 repo=InMemoryPaperExecutionObservationRepository();repo.save_many((obs(1),obs(2)));assert repo.count()==2;repo.clear();
 with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(repo.save,[obs(n) for n in range(4)]))
 assert repo.count()==4
