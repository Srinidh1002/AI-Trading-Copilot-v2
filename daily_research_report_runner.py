"""
Compatibility wrapper for the legacy public entry point.

Preserves the historical public API by exposing both the production
runner implementation and the legacy CLI entry point.
"""

# Business API
from services.daily_research_report_runner import *  # noqa: F401,F403

# Legacy CLI
from archive.daily_research_report_runner import main  # noqa: F401