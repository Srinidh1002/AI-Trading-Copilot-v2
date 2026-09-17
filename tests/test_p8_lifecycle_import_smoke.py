from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import (
    PaperPortfolioLifecycleCoordinator,
    project_paper_portfolio_position,
)
from services.paper_portfolio.paper_portfolio_replay_coordinator import (
    PaperPortfolioReplayCoordinator,
)


def test_lifecycle_symbols_import():
    assert PaperPortfolioLifecycleCoordinator is not None
    assert PaperPortfolioReplayCoordinator is not None
    assert callable(project_paper_portfolio_position)
