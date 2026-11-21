"""Consolidation export: staged lines rolled up to entity / account / period, in a flat
data-load layout similar to what consolidation tools (for example Oracle FCCS/HFM) import."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from ledger.db import Database

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
HEADER = ("Entity", "Account", "Year", "Period", "Scenario", "Currency", "Amount")


def export_consolidation(db: Database, out: str | Path) -> dict:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = db.rows(
        "SELECT company_code, account, fiscal_year, period, currency, SUM(amount) "
        "FROM stg.ledger GROUP BY company_code, account, fiscal_year, period, currency "
        "ORDER BY company_code, account, fiscal_year, period, currency"
    )
    total = Decimal("0")
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        for entity, account, year, period, currency, amount in rows:
            amount = Decimal(str(amount)).quantize(Decimal("0.01"))
            total += amount
            writer.writerow((entity, account, f"FY{int(year) % 100:02d}", MONTHS[int(period) - 1], "Actual", currency, f"{amount:.2f}"))
    # Journal entries must net to zero. Rejected lines leave their documents unbalanced:
    # report them so someone fixes the source instead of the totals drifting quietly.
    unbalanced = db.scalar(
        "SELECT COUNT(*) FROM (SELECT company_code, fiscal_year, document_no FROM stg.ledger "
        "GROUP BY company_code, fiscal_year, document_no HAVING ROUND(SUM(amount), 2) <> 0) d"
    )
    return {"file": str(out), "rows": len(rows), "net_total": f"{total:.2f}", "unbalanced_documents": unbalanced}
