"""Additive, side-effect-free canonical market analysis and decision APIs."""

from .analysis_pipeline import CanonicalAnalysisPipeline
from .decision_pipeline import CanonicalDecisionPipeline
from .pipeline import (
    CanonicalPipelineDependencies,
    run_canonical_analysis,
    run_canonical_pipeline,
)
from .comparison import (
    compare_dashboard_legacy_to_canonical,
    compare_live_option_legacy_to_canonical,
)
from .comparison_models import CanonicalLegacyComparison, ComparisonDifference

__all__ = [
    "CanonicalAnalysisPipeline",
    "CanonicalDecisionPipeline",
    "CanonicalPipelineDependencies",
    "run_canonical_analysis",
    "run_canonical_pipeline",
    "compare_dashboard_legacy_to_canonical",
    "compare_live_option_legacy_to_canonical",
    "CanonicalLegacyComparison",
    "ComparisonDifference",
]
