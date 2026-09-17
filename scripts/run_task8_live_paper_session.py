"""Repository-root wrapper for the Task 8 PAPER session CLI."""
from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
repository_root_text = str(REPOSITORY_ROOT)

if repository_root_text not in sys.path:
    sys.path.insert(0, repository_root_text)


from services.certification.task8_live_paper_session_cli import (
    main,
)


if __name__ == "__main__":
    raise SystemExit(main())
