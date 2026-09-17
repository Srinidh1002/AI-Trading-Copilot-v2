"""Canonical paper-candidate preparation and explicit execution boundaries."""

from .paper_candidate_service import (
    PaperCandidatePreparation,
    PaperCandidateStatus,
    PaperExecutionResult,
    execute_paper_candidate,
    prepare_paper_candidate,
)
from .authorization import validate_paper_execution_authorization
from .executor import execute_paper_order
from .idempotency import InMemoryPaperExecutionIdempotencyStore
from .execution_pipeline import run_canonical_paper_execution
from .order_repository import (
    DuplicatePaperOrderError,
    InMemoryPaperOrderRepository,
    InvalidPaperOrderTransitionError,
    PaperOrderNotFoundError,
    PaperOrderRepositoryError,
    StalePaperOrderStateError,
)
from .observation_repository import InMemoryPaperExecutionObservationRepository
from .observation_builder import build_paper_execution_observations
from .replay import replay_canonical_paper_execution

__all__ = [
    "PaperCandidatePreparation",
    "PaperCandidateStatus",
    "PaperExecutionResult",
    "prepare_paper_candidate",
    "execute_paper_candidate",
    "validate_paper_execution_authorization",
    "execute_paper_order",
    "InMemoryPaperExecutionIdempotencyStore",
    "run_canonical_paper_execution",
    "InMemoryPaperOrderRepository",
    "PaperOrderRepositoryError",
    "DuplicatePaperOrderError",
    "PaperOrderNotFoundError",
    "InvalidPaperOrderTransitionError",
    "StalePaperOrderStateError",
    "InMemoryPaperExecutionObservationRepository",
    "build_paper_execution_observations",
    "replay_canonical_paper_execution",
]
