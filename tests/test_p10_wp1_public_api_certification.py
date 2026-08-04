import services.dashboard_read_models as read_models


def test_public_api_matches_current_dashboard_boundary():
    assert tuple(read_models.__all__) == (
        "DashboardCycleViewV1",
        "DashboardMarketStateV1",
        "DashboardOpportunityViewV1",
        "DashboardPaperFillViewV1",
        "DashboardPaperPositionDetailViewV1",
        "DashboardPaperPositionViewV1",
        "DashboardPortfolioViewV1",
        "DashboardReadModelAssembler",
        "DashboardReadModelAssemblyInputV1",
        "DashboardRunnerHealthV1",
        "DashboardSystemSnapshotV1",
        "DashboardTradePlanTargetViewV1",
        "DashboardTradePlanViewV1",
        "DashboardValidationSummaryV1",
        "project_cycle_result",
        "project_paper_trade_fill",
        "project_paper_trade_position_detail",
        "project_paper_trade_snapshot",
        "project_portfolio_snapshot",
        "project_runtime_stats",
        "project_three_target_trade_plan",
        "project_trade_opportunity",
    )


def test_public_api_objects_are_resolvable():
    for name in read_models.__all__:
        assert getattr(read_models, name) is not None
