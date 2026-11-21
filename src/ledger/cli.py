"""Command line: ledger generate | run | export | runs | benchmark"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ledger.benchmark import benchmark, to_markdown
from ledger.db import opened
from ledger.export import export_consolidation
from ledger.generate import write_extract
from ledger.pipeline import METHODS, run

DEFAULT_DB = "sqlite:///data/ledger.db"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ledger", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="write a synthetic ERP ledger extract (CSV, ';' separated)")
    g.add_argument("--rows", type=int, default=170_000)
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--defect-rate", type=float, default=0.003)
    g.add_argument("--out", default="data/ledger_extract.csv")

    r = sub.add_parser("run", help="validate and load an extract into stg.ledger, audited in ctl.*")
    r.add_argument("source")
    r.add_argument("--db", default=DEFAULT_DB)
    r.add_argument("--method", choices=METHODS, default="batch")
    r.add_argument("--force", action="store_true", help="reload even if this file already loaded")

    e = sub.add_parser("export", help="write the consolidation data-load file")
    e.add_argument("--db", default=DEFAULT_DB)
    e.add_argument("--out", default="out/consolidation_load.csv")

    ls = sub.add_parser("runs", help="list runs from ctl.runs")
    ls.add_argument("--db", default=DEFAULT_DB)

    b = sub.add_parser("benchmark", help="compare load methods on the same extract")
    b.add_argument("source")
    b.add_argument("--db", default=None, help="server URL (default: fresh SQLite files)")
    b.add_argument("--methods", default="row,batch")
    b.add_argument("--out", default=None, help="also write the markdown table here")

    a = p.parse_args(argv)

    if a.cmd == "generate":
        rep = write_extract(a.out, a.rows, seed=a.seed, defect_rate=a.defect_rate)
        print(json.dumps({"file": a.out, "rows": rep.rows, "documents": rep.documents,
                          "injected_defects": rep.defects, "defect_total": rep.defect_total}, indent=2))
    elif a.cmd == "run":
        with opened(a.db) as db:
            res = run(db, a.source, method=a.method, force=a.force)
        print(json.dumps(res.__dict__, indent=2))
    elif a.cmd == "export":
        with opened(a.db) as db:
            print(json.dumps(export_consolidation(db, a.out), indent=2))
    elif a.cmd == "runs":
        with opened(a.db) as db:
            rows = db.rows(
                "SELECT run_id, source_file, method, status, rows_read, rows_loaded, rows_rejected, "
                "load_seconds, started_at FROM ctl.runs ORDER BY started_at"
            )
        for row in rows:
            print(" | ".join("" if v is None else str(v) for v in row))
    elif a.cmd == "benchmark":
        methods = tuple(m.strip() for m in a.methods.split(","))
        res = benchmark(Path(a.source), a.db, methods)
        table = to_markdown(res, "SQL Server" if a.db else "SQLite")
        print(table)
        if a.out:
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out).write_text(table, encoding="utf-8")
    return 0
