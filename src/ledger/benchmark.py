"""Load benchmark: the same extract loaded row by row and in batches, each into a fresh database."""

from __future__ import annotations

import platform
import tempfile
from pathlib import Path

from ledger.db import connect
from ledger.pipeline import run
from ledger.schema import drop_schema


def benchmark(source: Path, url: str | None, methods: tuple[str, ...]) -> list[dict]:
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for method in methods:
            db_url = url or f"sqlite:///{Path(tmp) / f'bench_{method}.db'}"
            db = connect(db_url)
            try:
                if url:  # shared server database: start clean each time
                    drop_schema(db)
                res = run(db, source, method=method, force=True)
            finally:
                db.close()
            rate = res.rows_loaded / res.load_seconds if res.load_seconds else float("inf")
            results.append(
                {"method": method, "rows": res.rows_loaded, "load_seconds": res.load_seconds, "rows_per_second": round(rate)}
            )
    return results


def to_markdown(results: list[dict], backend: str) -> str:
    base = next((r for r in results if r["method"] == "row"), None)
    lines = [
        f"Backend: {backend} · Python {platform.python_version()} · {platform.system()} {platform.machine()}",
        "",
        "| Method | Rows loaded | Load time (s) | Rows/s | Speed-up vs row |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in results:
        speed = f"{base['load_seconds'] / r['load_seconds']:.1f}x" if base and r["load_seconds"] else "-"
        lines.append(f"| {r['method']} | {r['rows']:,} | {r['load_seconds']:.2f} | {r['rows_per_second']:,} | {speed} |")
    return "\n".join(lines) + "\n"
