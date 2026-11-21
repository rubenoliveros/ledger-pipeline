import pytest

from ledger.db import connect
from ledger.generate import write_extract


@pytest.fixture
def db():
    database = connect("sqlite:///:memory:")
    yield database
    database.close()


@pytest.fixture
def extract(tmp_path):
    path = tmp_path / "extract.csv"
    report = write_extract(path, rows=3_000, seed=7, defect_rate=0.02)
    return path, report
