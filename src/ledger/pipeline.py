"""The audited load: extract file -> validation -> stg.ledger, with every run recorded in ctl.*.

Guarantees
- Every run has a RunID in ctl.runs with counts, timings and final status.
- Every rejected line is kept in ctl.rejects with a reason, so rows_read = rows_loaded + rows_rejected.
- Reruns are idempotent: loading the same file again is a no-op unless forced, and a forced
  rerun first removes what earlier runs of that file loaded. Nothing is lost, nothing doubles.
"""

from __future__ import annotations

import csv
import hashlib
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ledger.db import Database
from ledger.schema import create_schema
from ledger.validate import CleanRow, Rejected, clean, raw_line

METHODS = ("row", "batch", "fast")
BATCH_SIZE = 5_000

INSERT_LEDGER = (
    "INSERT INTO stg.ledger (run_id, company_code, fiscal_year, period, document_no, line_item, "
    "posting_date, account, cost_center, currency, amount, text) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
)
INSERT_REJECT = "INSERT INTO ctl.rejects (run_id, line_no, reason, raw_line) VALUES (?,?,?,?)"


@dataclass
class RunResult:
    run_id: str
    status: str
    rows_read: int = 0
    rows_loaded: int = 0
    rows_rejected: int = 0
    load_seconds: float = 0.0
    total_seconds: float = 0.0
    skipped: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _load(db: Database, run_id: str, rows: list[CleanRow], method: str) -> None:
    cur = db.cursor()
    if method == "row":
        # One statement and one commit per line: the pattern that made the original run take 15 minutes.
        for row in rows:
            cur.execute(INSERT_LEDGER, row.as_params(run_id))
            db.commit()
        return
    if method == "fast":
        if db.dialect != "mssql":
            raise ValueError("method 'fast' uses pyodbc fast_executemany and needs SQL Server")
        cur.fast_executemany = True
    for chunk in _chunks(rows, BATCH_SIZE):
        cur.executemany(INSERT_LEDGER, [r.as_params(run_id) for r in chunk])
    db.commit()


def run(db: Database, source: str | Path, method: str = "batch", force: bool = False) -> RunResult:
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    source = Path(source)
    started = time.perf_counter()
    create_schema(db)
    digest = file_hash(source)

    done = db.scalar(
        "SELECT run_id FROM ctl.runs WHERE file_hash = ? AND status = 'SUCCESS' ORDER BY started_at DESC",
        (digest,),
    )
    if done and not force:
        return RunResult(run_id=done, status="SKIPPED", skipped=True)

    run_id = str(uuid.uuid4())
    cur = db.cursor()

    previous = [r[0] for r in db.rows("SELECT run_id FROM ctl.runs WHERE file_hash = ?", (digest,))]
    cur.execute(
        "INSERT INTO ctl.runs (run_id, source_file, file_hash, method, status, started_at) VALUES (?,?,?,?,?,?)",
        (run_id, source.name, digest, method, "RUNNING", _now()),
    )
    db.commit()

    result = RunResult(run_id=run_id, status="RUNNING")
    try:
        # Idempotent rerun: remove what earlier runs of this same file loaded. Not committed yet,
        # so with the batch methods a failure rolls back to the previous good state.
        for old in previous:
            cur.execute("DELETE FROM stg.ledger WHERE run_id = ?", (old,))
            cur.execute("DELETE FROM ctl.rejects WHERE run_id = ?", (old,))
            cur.execute("UPDATE ctl.runs SET status = 'SUPERSEDED' WHERE run_id = ?", (old,))

        existing = set(db.rows("SELECT company_code, fiscal_year, document_no, line_item FROM stg.ledger"))
        good: list[CleanRow] = []
        rejects: list[tuple] = []
        seen: set[tuple] = set()
        with source.open(newline="", encoding="utf-8") as fh:
            for line_no, raw in enumerate(csv.DictReader(fh, delimiter=";"), start=2):
                result.rows_read += 1
                try:
                    row = clean(raw)
                    if row.key in seen:
                        raise Rejected("duplicate_key_in_file")
                    if row.key in existing:
                        raise Rejected("key_already_loaded")
                except Rejected as rej:
                    rejects.append((run_id, line_no, rej.reason, raw_line(raw)))
                    continue
                seen.add(row.key)
                good.append(row)

        t0 = time.perf_counter()
        _load(db, run_id, good, method)
        result.load_seconds = round(time.perf_counter() - t0, 3)

        for chunk in _chunks(rejects, BATCH_SIZE):
            cur.executemany(INSERT_REJECT, chunk)
        result.rows_loaded = len(good)
        result.rows_rejected = len(rejects)
        result.total_seconds = round(time.perf_counter() - started, 3)
        result.status = "SUCCESS"
        cur.execute(
            "UPDATE ctl.runs SET status = ?, finished_at = ?, rows_read = ?, rows_loaded = ?, rows_rejected = ?, "
            "load_seconds = ?, total_seconds = ? WHERE run_id = ?",
            (result.status, _now(), result.rows_read, result.rows_loaded, result.rows_rejected,
             result.load_seconds, result.total_seconds, run_id),
        )
        db.commit()
        return result
    except Exception as exc:
        db.conn.rollback()
        db.cursor().execute(
            "UPDATE ctl.runs SET status = 'FAILED', finished_at = ?, error = ? WHERE run_id = ?",
            (_now(), f"{type(exc).__name__}: {exc}"[:4000], run_id),
        )
        db.commit()
        raise
