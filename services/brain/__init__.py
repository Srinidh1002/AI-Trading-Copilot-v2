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

__all__ = [
    "ANALYZER_CATEGORIES",
    "RUNTIME_ROLES",
    "SOURCE_FAMILIES",
    "SUPPORTED_MARKETS",
    "AnalyzerDescriptorV1",
    "AnalyzerRegistryV1",
    "DEFAULT_ANALYZER_REGISTRY_V1",
]