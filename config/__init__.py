"""Compatibility exports for the historical root-level ``config.py`` module.

Python resolves the ``config`` package before the adjacent ``config.py`` file.
Existing callers use ``from config import ...`` for values defined in that
historical module, so load it once under an internal module name and expose its
public constants here. The package's version metadata remains authoritative
for its established callers.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


_ROOT_CONFIG_MODULE = "_ai_trading_copilot_root_config"
_ROOT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.py"
_root_config = sys.modules.get(_ROOT_CONFIG_MODULE)

if _root_config is None:
    _spec = spec_from_file_location(
        _ROOT_CONFIG_MODULE,
        _ROOT_CONFIG_PATH,
    )
    if _spec is None or _spec.loader is None:
        raise ImportError(
            f"Unable to load compatibility configuration from {_ROOT_CONFIG_PATH}"
        )
    _root_config = module_from_spec(_spec)
    sys.modules[_ROOT_CONFIG_MODULE] = _root_config
    _spec.loader.exec_module(_root_config)

for _name in dir(_root_config):
    if _name.isupper():
        globals()[_name] = getattr(_root_config, _name)

from .version import (  # noqa: E402
    APP_NAME,
    VERSION,
    PHASE,
    BUILD,
)

__all__ = sorted(name for name in globals() if name.isupper())
