"""Runtime settings, read from environment variables (or a local .env file)."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env = BASE_DIR / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()

DATA_DIR = Path(os.getenv("INVOICEIQ_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'invoiceiq.db'}")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
# "auto" uses Claude when a key is set and falls back to the rule-based extractor otherwise.
EXTRACTOR = os.getenv("EXTRACTOR", "auto").lower()

# Tolerance (in currency units) when checking that amounts add up.
AMOUNT_TOLERANCE = float(os.getenv("AMOUNT_TOLERANCE", "0.02"))
