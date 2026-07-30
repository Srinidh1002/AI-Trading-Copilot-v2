import services.dashboard_read_models as read_models


def test_public_api_matches_wp1_boundary():
    assert tuple(read_models.__all__) == (
        "DashboardCycleViewV1",
        "DashboardMarketStateV1",
        "DashboardPaperPositionViewV1",
        "DashboardPortfolioViewV1",
        "DashboardReadModelAssembler",
        "DashboardReadModelAssemblyInputV1",
        "DashboardRunnerHealthV1",
        "DashboardSystemSnapshotV1",
        "DashboardValidationSummaryV1",
        "project_cycle_result",
        "project_paper_trade_snapshot",
        "project_portfolio_snapshot",
        "project_runtime_stats",
    )


def test_public_api_objects_are_resolvable():
    for name in read_models.__all__:
        assert getattr(read_models, name) is not None
