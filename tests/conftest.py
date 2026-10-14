import os
import tempfile
from pathlib import Path

import pytest

# Isolated data dir + forced offline extractor, set before the app is imported.
_tmp = tempfile.mkdtemp(prefix="invoiceiq-test-")
os.environ["INVOICEIQ_DATA_DIR"] = _tmp
os.environ["EXTRACTOR"] = "rules"

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from sqlmodel import SQLModel

    from app.db import engine
    from app.main import app

    SQLModel.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c


def sample(name: str) -> Path:
    return next(SAMPLES.glob(f"{name}*.pdf"))
