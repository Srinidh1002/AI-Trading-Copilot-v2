"""Zero-authority Brain research infrastructure.

Nothing in ``services.brain`` has execution, risk, position-management,
certification, or broker-submission authority.
"""

from .analyzer_registry_v1 import (
    ANALYZER_CATEGORIES,
    RUNTIME_ROLES,
    SOURCE_FAMILIES,
    SUPPORTED_MARKETS,
    AnalyzerDescriptorV1,
    AnalyzerRegistryV1,
    DEFAULT_ANALYZER_REGISTRY_V1,
)
from .source_adapters_v1 import (
    IndexNewsSourceV1,
    IndexPremarketSourceV1,
    IndexTechnicalSourceV1,
    McxNativeSourceV1,
    adapt_index_news_v1,
    adapt_index_premarket_v1,
    adapt_index_technical_v1,
    adapt_mcx_native_v1,
)

__all__ = [
    "ANALYZER_CATEGORIES",
    "RUNTIME_ROLES",
    "SOURCE_FAMILIES",
    "SUPPORTED_MARKETS",
    "AnalyzerDescriptorV1",
    "AnalyzerRegistryV1",
    "DEFAULT_ANALYZER_REGISTRY_V1",
    "IndexNewsSourceV1",
    "IndexPremarketSourceV1",
    "IndexTechnicalSourceV1",
    "McxNativeSourceV1",
    "adapt_index_news_v1",
    "adapt_index_premarket_v1",
    "adapt_index_technical_v1",
    "adapt_mcx_native_v1",
]