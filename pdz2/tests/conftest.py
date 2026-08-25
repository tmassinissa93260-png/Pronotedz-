from __future__ import annotations

import sys
from pathlib import Path

# Le paquet est utilisable depuis un dépôt non installé.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pdz2.contracts  # noqa: E402,F401  (enregistre tous les contrats)
