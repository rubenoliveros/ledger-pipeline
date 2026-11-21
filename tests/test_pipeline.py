import pytest

from ledger.export import export_consolidation
from ledger.generate import write_extract
from ledger.pipeline import run


def counts(db):
    return db.scalar("SELECT COUNT(*) FROM stg.ledger"), db.scalar("SELECT COUNT(*) FROM ctl.rejects")


@pytest.mark.parametrize("method", ["row", "batch"])
def test_every_row_accounted_for(db, extract, method):
    path, report = extract
    res = run(db, path, method=method)
    assert res.status == "SUCCESS"
    assert res.rows_read == report.rows
    assert res.rows_loaded + res.rows_rejected == res.rows_read
    assert counts(db) == (res.rows_loaded, res.rows_rejected)
    run_row = db.rows("SELECT status, rows_read, rows_loaded, rows_rejected FROM ctl.runs WHERE run_id = ?", (res.run_id,))
    assert run_row == [("SUCCESS", res.rows_read, res.rows_loaded, res.rows_rejected)]


def test_rerun_same_file_is_skipped(db, extract):
    path, _ = extract
    first = run(db, path)
    second = run(db, path)
    assert second.skipped and second.run_id == first.run_id
    assert counts(db)[0] == first.rows_loaded


def test_forced_rerun_never_duplicates(db, extract):
    path, _ = extract
    first = run(db, path)
    again = run(db, path, force=True)
    assert again.run_id != first.run_id
    assert counts(db) == (again.rows_loaded, again.rows_rejected)
    statuses = dict(db.rows("SELECT run_id, status FROM ctl.runs"))
    assert statuses == {first.run_id: "SUPERSEDED", again.run_id: "SUCCESS"}


def test_overlapping_file_rejects_already_loaded_keys(db, tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    write_extract(a, 1_000, seed=11, defect_rate=0.0)
    write_extract(b, 1_500, seed=11, defect_rate=0.0)  # same first 1,000 lines plus 500 new ones
    run(db, a)
    res = run(db, b)
    reasons = dict(db.rows("SELECT reason, COUNT(*) FROM ctl.rejects WHERE run_id = ? GROUP BY reason", (res.run_id,)))
    assert reasons == {"key_already_loaded": 1_000}
    assert res.rows_loaded == 500


def test_failed_batch_run_rolls_back(db, extract, monkeypatch):
    path, _ = extract
    good = run(db, path)
    before = counts(db)

    import ledger.pipeline as pipeline

    def boom(*args, **kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr(pipeline, "_load", boom)
    with pytest.raises(RuntimeError):
        run(db, path, force=True)
    assert counts(db) == before  # previous good load is intact
    failed = db.rows("SELECT status, error FROM ctl.runs WHERE run_id <> ?", (good.run_id,))
    assert failed[0][0] == "FAILED" and "database went away" in failed[0][1]
    assert db.scalar("SELECT status FROM ctl.runs WHERE run_id = ?", (good.run_id,)) == "SUCCESS"


def test_export_totals_match_staging(db, extract, tmp_path):
    path, _ = extract
    run(db, path)
    summary = export_consolidation(db, tmp_path / "load.csv")
    staged = db.scalar("SELECT ROUND(SUM(amount), 2) FROM stg.ledger")
    assert float(summary["net_total"]) == pytest.approx(float(staged), abs=0.01)
    assert summary["unbalanced_documents"] > 0  # rejected lines leave their documents unbalanced
    lines = (tmp_path / "load.csv").read_text().splitlines()
    assert lines[0] == "Entity,Account,Year,Period,Scenario,Currency,Amount"
    assert len(lines) - 1 == summary["rows"]
