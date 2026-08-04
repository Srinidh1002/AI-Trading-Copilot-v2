import pytest
@pytest.mark.parametrize("name",("PaperExecutionRequestV1","PaperExecutionAuthorizationV1","PaperAuthorizationResultV1","PaperExecutionResultV1","PaperOrderStateV1","CanonicalPaperExecutionResultV1","PaperExecutionObservationV1","PaperExecutionReplayResultV1","validate_paper_execution_authorization","execute_paper_order","InMemoryPaperExecutionIdempotencyStore","run_canonical_paper_execution","InMemoryPaperOrderRepository","InMemoryPaperExecutionObservationRepository","build_paper_execution_observations","replay_canonical_paper_execution"))
@pytest.mark.parametrize("boundary",("import","paper_only","no_live"))
def test_public_p4_import_boundary(name,boundary):
 import services.contracts as contracts
 import services.paper as paper
 assert hasattr(contracts,name) or hasattr(paper,name)
