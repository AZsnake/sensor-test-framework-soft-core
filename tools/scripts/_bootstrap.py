"""Add ``tools/`` and ``tools/lib`` to ``sys.path`` for CLI scripts."""
from __future__ import annotations

import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent.parent
for _p in (_TOOLS_DIR, _TOOLS_DIR / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
