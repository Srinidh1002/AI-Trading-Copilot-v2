import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from services.certification.task1c_parent_only_live_canary_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
