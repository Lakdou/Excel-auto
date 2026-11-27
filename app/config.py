"""Configuration par variables d'environnement."""

from __future__ import annotations

import os
from pathlib import Path

MAX_UPLOAD_MB = int(os.environ.get("EXCEL_AUTO_MAX_UPLOAD_MB", "50"))
DATA_DIR = Path(os.environ.get("EXCEL_AUTO_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
# Si défini, les applications générées (qui contiennent des données) exigent ce code d'accès.
ACCESS_CODE = os.environ.get("EXCEL_AUTO_ACCESS_CODE") or None
