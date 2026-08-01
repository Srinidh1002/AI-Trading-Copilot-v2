"""Stable, versioned contracts shared across runtime boundaries.

Exports are resolved lazily so a consumer of a small contract does not load
unrelated legacy contracts or their optional runtime dependencies.
"""
from __future__ import annotations
from importlib import import_module

_EXPORTS = {
 "entry_zone_evaluation_input_v1":("EntryZoneEvaluationInputV1",),"entry_zone_evaluation_result_v1":("EntryZoneEvaluationResultV1",),
 "stop_loss_evaluation_input_v1":("StopLossEvaluationInputV1",),"stop_loss_evaluation_result_v1":("StopLossEvaluationResultV1",),
 "three_target_evaluation_input_v1":("ThreeTargetEvaluationInputV1",),"three_target_evaluation_result_v1":("ThreeTargetEvaluationResultV1",),
 "option_contract_selection_input_v1":("OptionContractSelectionInputV1",),
 "option_contract_selection_result_v1":("OptionContractSelectionResultV1",),
 "option_contract_eligibility_evidence_v1":("OptionContractEligibilityEvidenceV1",),
 "three_target_trade_plan_v1":("ThreeTargetTradePlanV1",),
 "trade_plan_target_v1":("TradePlanTargetV1",),
 "trade_planning_policy_v1":("TradePlanningPolicyV1",),
 "capital_quantity_planning_policy_v1":("CapitalQuantityPlanningPolicyV1",),
 "capital_quantity_planning_input_v1":("CapitalQuantityPlanningInputV1",),
 "capital_quantity_planning_result_v1":("CapitalQuantityPlanningResultV1",),
 "capital_quantity_trading_cost_policy_v1":("CapitalQuantityTradingCostPolicyV1",),"capital_quantity_trading_cost_evidence_v1":("CapitalQuantityTradingCostEvidenceV1",),
 "integrated_three_target_trade_plan_input_v1":("IntegratedThreeTargetTradePlanInputV1",),"integrated_three_target_trade_plan_result_v1":("IntegratedThreeTargetTradePlanResultV1",),
 "paper_trade_lifecycle_policy_v1":("PaperTradeLifecyclePolicyV1",),"paper_trade_lifecycle_state_v1":("PaperTradeLifecycleStateV1","is_legal_paper_trade_lifecycle_transition","CANONICAL_PAPER_TRADE_LIFECYCLE_STATES","TERMINAL_PAPER_TRADE_LIFECYCLE_STATES"),
 "paper_market_observation_v1":("PaperMarketObservationV1",),"paper_trade_fill_v1":("PaperTradeFillV1",),"paper_trade_position_v1":("PaperTradePositionV1",),"paper_trade_entry_evaluation_input_v1":("PaperTradeEntryEvaluationInputV1",),"paper_trade_entry_evaluation_result_v1":("PaperTradeEntryEvaluationResultV1",),
 "paper_trade_pnl_evidence_v1":("PaperTradePnlEvidenceV1",),"paper_trade_position_evaluation_input_v1":("PaperTradePositionEvaluationInputV1",),"paper_trade_position_evaluation_result_v1":("PaperTradePositionEvaluationResultV1",),
 "paper_trade_persistence_snapshot_v1":("PaperTradePersistenceSnapshotV1",),
 "paper_portfolio_policy_v1":("PaperPortfolioPolicyV1",),
 "paper_capital_reservation_v1":("PaperCapitalReservationV1",),
 "paper_portfolio_position_reference_v1":("PaperPortfolioPositionReferenceV1",),
 "paper_portfolio_exposure_v1":("PaperPortfolioExposureV1",),
 "paper_portfolio_lock_state_v1":("PaperPortfolioLockStateV1",),
 "paper_portfolio_snapshot_v1":("PaperPortfolioSnapshotV1",),
 "paper_portfolio_admission_input_v1":("PaperPortfolioAdmissionInputV1",),
 "paper_portfolio_admission_result_v1":("PaperPortfolioAdmissionResultV1",),
 "paper_portfolio_update_input_v1":("PaperPortfolioUpdateInputV1",),
 "paper_portfolio_update_result_v1":("PaperPortfolioUpdateResultV1",),
 "paper_portfolio_persistence_snapshot_v1":("PaperPortfolioPersistenceSnapshotV1",),
 "paper_portfolio_recovery_result_v1":("PaperPortfolioRecoveryResultV1",),
 "canonical_trade_plan_input_v1":("CanonicalTradePlanInputV1",),
 "market_snapshot_v1":("DataStatus","MarketSnapshotV1","OHLCVBar","OHLCVSeries","SnapshotValidationError","from_core_snapshot","from_dashboard_snapshot","from_live_analysis_inputs","normalise_ohlcv","to_legacy_dashboard_dict","to_lowercase_ohlcv","to_uppercase_ohlcv"),
 "analysis_result_v1":("AlignmentStatus","AnalysisResultV1","AnalysisValidationError","DirectionalBias","EvidenceSection","EvidenceSignal","EvidenceStatus","MarketRegime","MultiTimeframeSummary","TimeframeState"),
 "final_decision_v1":("Action","AuthorizationStatus","DataHealthSummary","DecisionValidationError","ExecutionStatus","FinalDecisionV1","RiskSummary","TradePlanV1","from_live_option_pipeline_response","from_master_decision_response","from_trade_engine_response"),
 "runtime_adapters":("build_dashboard_decision_v1","build_dashboard_shadow_contracts","build_dashboard_snapshot_v1","build_live_option_decision_v1","build_live_option_shadow_contracts","build_live_option_snapshot_v1","compare_shadow_contracts","serialize_shadow_contracts","validate_shadow_contracts"),
 "paper_trade_candidate_v1":("PaperCandidateValidationError","PaperTradeCandidateV1"),"replay_fixture_v1":("ReplayExpectationsV1","ReplayFixtureV1","ReplayFixtureValidationError"),"audit_event_v1":("AuditEventV1",),"paper_execution_request_v1":("PaperExecutionRequestV1",),"paper_execution_result_v1":("PaperExecutionResultV1",),"paper_order_state_v1":("PaperOrderStateV1",),"paper_execution_authorization_v1":("PaperExecutionAuthorizationV1",),"paper_authorization_result_v1":("PaperAuthorizationResultV1",),"canonical_paper_execution_result_v1":("CanonicalPaperExecutionResultV1",),"paper_execution_observation_v1":("PaperExecutionObservationV1",),"paper_execution_replay_result_v1":("PaperExecutionReplayResultV1",),
 "market_instrument_v1":("MarketInstrumentV1",),"market_universe_v1":("MarketUniverseV1",),"provider_market_mapping_v1":("ProviderMarketMappingV1",),"market_data_provenance_v1":("MarketDataProvenanceV1",),"market_quote_v1":("MarketQuoteV1",),"market_candle_v1":("MarketCandleV1",),"market_candle_series_v1":("MarketCandleSeriesV1",),"market_data_quality_result_v1":("MarketDataQualityResultV1",),"market_data_freshness_policy_v1":("MarketDataFreshnessPolicyV1",),"timeframe_evidence_v1":("TimeframeEvidenceV1",),"multi_timeframe_snapshot_v1":("MultiTimeframeSnapshotV1",),"multi_timeframe_quality_result_v1":("MultiTimeframeQualityResultV1",),"multi_timeframe_policy_v1":("MultiTimeframePolicyV1",),"technical_indicator_value_v1":("TechnicalIndicatorValueV1",),"timeframe_technical_evidence_v1":("TimeframeTechnicalEvidenceV1",),"technical_intelligence_result_v1":("TechnicalIntelligenceResultV1",),"technical_intelligence_policy_v1":("TechnicalIntelligencePolicyV1","DEFAULT_TECHNICAL_INTELLIGENCE_POLICY"),"market_session_validation_v1":("MarketSessionValidationV1",),"option_quote_v1":("OptionQuoteV1",),"option_strike_row_v1":("OptionStrikeRowV1",),"option_chain_snapshot_v1":("OptionChainSnapshotV1",),"option_chain_quality_result_v1":("OptionChainQualityResultV1",),"option_chain_policy_v1":("OptionChainPolicyV1","DEFAULT_OPTION_CHAIN_POLICY"),"option_chain_metric_v1":("OptionChainMetricV1",),"option_chain_intelligence_policy_v1":("OptionChainIntelligencePolicyV1","DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY"),"option_chain_intelligence_result_v1":("OptionChainIntelligenceResultV1",),"option_contract_v1":("OptionContractV1",),"option_contract_universe_v1":("OptionContractUniverseV1",),"selected_option_contract_v1":("SelectedOptionContractV1",),"trade_plan_v1":("TradePlanV1",),"canonical_trade_plan_result_v1":("CanonicalTradePlanResultV1",),"risk_policy_v1":("RiskPolicyV1",),"position_size_result_v1":("PositionSizeResultV1",),"canonical_risk_result_v1":("CanonicalRiskResultV1",),
 "services.options.policies":("OptionSelectionPolicy","TradePlanPolicy"),
 "option_contract_candidate_v1": (
    "OptionContractCandidateV1",
),
"option_contract_ranking_policy_v1": (
    "OptionContractRankingPolicyV1",
    "DEFAULT_OPTION_CONTRACT_RANKING_POLICY",
),
"option_contract_ranking_result_v1": (
    "OptionContractRankingResultV1",
),
"trade_opportunity_v1": (
    "TradeOpportunityV1",
),
"trade_opportunity_policy_v1": (
    "TradeOpportunityPolicyV1",
    "DEFAULT_TRADE_OPPORTUNITY_POLICY",
),
"cross_market_evidence_v1": ("CrossMarketEvidenceV1",),
"market_breadth_evidence_v1": ("MarketBreadthEvidenceV1",),
"volatility_context_v1": ("VolatilityContextV1",),
"broader_market_intelligence_result_v1": (
    "BroaderMarketIntelligenceResultV1",
),
"broader_market_intelligence_policy_v1": (
    "BroaderMarketIntelligencePolicyV1",
    "DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY",
),
"market_breadth_snapshot_v1": ("MarketBreadthSnapshotV1",),
"volatility_snapshot_v1": ("VolatilitySnapshotV1",),
"external_market_observation_v1": ("ExternalMarketObservationV1",),
"institutional_flow_snapshot_v1": ("InstitutionalFlowSnapshotV1",),
"scheduled_market_event_v1": ("ScheduledMarketEventV1",),
"external_context_policy_v1": ("ExternalContextPolicyV1", "DEFAULT_EXTERNAL_CONTEXT_POLICY"),
"global_market_context_result_v1": ("GlobalMarketContextResultV1",),
"institutional_flow_context_result_v1": ("InstitutionalFlowContextResultV1",),
"event_risk_context_result_v1": ("EventRiskContextResultV1",),
"external_market_context_result_v1": ("ExternalMarketContextResultV1",),
"canonical_market_regime_result_v1": ("CanonicalMarketRegimeResultV1",),
"market_regime_policy_v1": ("MarketRegimePolicyV1","DEFAULT_MARKET_REGIME_POLICY"),
"technical_regime_component_result_v1": ("TechnicalRegimeComponentResultV1",),
"broader_market_regime_component_result_v1": ("BroaderMarketRegimeComponentResultV1",),
"external_context_regime_component_result_v1": ("ExternalContextRegimeComponentResultV1",),
"market_regime_input_v1": ("MarketRegimeInputV1",),
"market_opportunity_candidate_v1": ("MarketOpportunityCandidateV1",),
"market_analysis_candidate_v1": ("MarketAnalysisCandidateV1","MarketAnalysisEvidenceV1"),
"four_market_ranking_policy_v1": ("FourMarketRankingPolicyV1","DEFAULT_FOUR_MARKET_RANKING_POLICY"),
"four_market_opportunity_ranking_result_v1": ("FourMarketOpportunityRankingResultV1",),
"paper_orchestration_policy_v1":("PaperOrchestrationPolicyV1",),
"paper_orchestration_failure_v1":("PaperOrchestrationFailureV1",),
"paper_orchestration_stage_result_v1":("PaperOrchestrationStageResultV1",),
"paper_orchestration_cycle_input_v1":("PaperOrchestrationCycleInputV1",),
"paper_orchestration_cycle_result_v1":("PaperOrchestrationCycleResultV1",),
"paper_orchestration_journal_record_v1":("PaperOrchestrationJournalRecordV1",),
}
_ALIASES={"decision_to_legacy_dashboard_dict":("final_decision_v1","to_legacy_dashboard_dict")}
__all__=[name for names in _EXPORTS.values() for name in names]+list(_ALIASES)

def __getattr__(name: str):
    for module,names in _EXPORTS.items():
        if name in names:
            value=getattr(import_module(module if module.startswith("services.") else f"{__name__}.{module}"),name)
            globals()[name]=value
            return value
    if name in _ALIASES:
        module,attribute=_ALIASES[name];value=getattr(import_module(f"{__name__}.{module}"),attribute);globals()[name]=value;return value
    raise AttributeError(name)

def __dir__(): return sorted(set(globals())|set(__all__))
