"""
Project-wide pytest configuration.

Ensures the project root is always on sys.path so absolute imports
like `import services` work regardless of how pytest is invoked.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
project_root_str = str(PROJECT_ROOT)

if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)