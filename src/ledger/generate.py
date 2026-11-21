"""Synthetic ERP ledger extract generator.

Produces balanced journal entries (each document's lines sum to zero) and
injects a small, known share of defects so data quality checks have work to do.
Same seed, same file.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from ledger.reference import ACCOUNTS, COST_CENTERS, CURRENCIES, ENTITIES, EXTRACT_COLUMNS

DEFECT_KINDS = ("missing_account", "unknown_account", "bad_date", "bad_amount", "duplicate_key")


@dataclass
class GenerationReport:
    rows: int = 0
    documents: int = 0
    defects: dict[str, int] = field(default_factory=lambda: {k: 0 for k in DEFECT_KINDS})

    @property
    def defect_total(self) -> int:
        return sum(self.defects.values())


def _documents(rng: random.Random, fiscal_year: int):
    accounts = list(ACCOUNTS)
    entities = list(ENTITIES)
    doc_no = 1_000_000
    while True:
        doc_no += 1
        entity = rng.choice(entities)
        period = rng.randint(1, 12)
        day = rng.randint(1, 28)
        posting = date(fiscal_year, period, day)
        currency = CURRENCIES[0] if rng.random() < 0.85 else CURRENCIES[1]
        n_lines = rng.choice((2, 2, 2, 3, 4, 6))
        amounts = [round(rng.uniform(10, 25_000), 2) for _ in range(n_lines - 1)]
        amounts.append(round(-sum(amounts), 2))  # balancing line
        lines = []
        for i, amount in enumerate(amounts, start=1):
            lines.append(
                {
                    "company_code": entity,
                    "fiscal_year": str(fiscal_year),
                    "period": f"{period:02d}",
                    "document_no": str(doc_no),
                    "line_item": f"{i:03d}",
                    "posting_date": posting.isoformat(),
                    "account": rng.choice(accounts),
                    "cost_center": rng.choice(COST_CENTERS),
                    "currency": currency,
                    "amount": f"{amount:.2f}",
                    "text": f"Synthetic entry {doc_no}-{i}",
                }
            )
        yield lines


def _corrupt(row: dict[str, str], kind: str, rng: random.Random) -> dict[str, str]:
    row = dict(row)
    if kind == "missing_account":
        row["account"] = ""
    elif kind == "unknown_account":
        row["account"] = "9999"
    elif kind == "bad_date":
        row["posting_date"] = rng.choice(("2026-02-30", "31/12/2026", "not-a-date"))
    elif kind == "bad_amount":
        row["amount"] = rng.choice(("12,50", "N/A", ""))
    return row


def generate_rows(rows: int, seed: int = 42, defect_rate: float = 0.003, fiscal_year: int = 2026):
    """Yield (row_dict, defect_kind_or_None) until `rows` rows were produced."""
    rng = random.Random(seed)
    produced = 0
    previous: dict[str, str] | None = None
    for doc in _documents(rng, fiscal_year):
        for line in doc:
            if produced >= rows:
                return
            kind = None
            if rng.random() < defect_rate:
                kind = rng.choice(DEFECT_KINDS)
                if kind == "duplicate_key" and previous is not None:
                    line = dict(previous)  # exact repeat of the previous line's business key
                elif kind == "duplicate_key":
                    kind = None
                else:
                    line = _corrupt(line, kind, rng)
            produced += 1
            previous = line
            yield line, kind


def write_extract(path: str | Path, rows: int, seed: int = 42, defect_rate: float = 0.003) -> GenerationReport:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    report = GenerationReport()
    seen_docs: set[str] = set()
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=EXTRACT_COLUMNS, delimiter=";")
        writer.writeheader()
        for row, kind in generate_rows(rows, seed=seed, defect_rate=defect_rate):
            writer.writerow(row)
            report.rows += 1
            seen_docs.add(row["document_no"])
            if kind:
                report.defects[kind] += 1
    report.documents = len(seen_docs)
    return report
