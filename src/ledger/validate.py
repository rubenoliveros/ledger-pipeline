"""Row-level data quality checks. Each failed row becomes a ctl.rejects entry with a reason."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from ledger.reference import ACCOUNTS, CURRENCIES, ENTITIES, EXTRACT_COLUMNS

REQUIRED = ("company_code", "fiscal_year", "period", "document_no", "line_item", "posting_date", "account", "amount")


@dataclass(frozen=True)
class CleanRow:
    company_code: str
    fiscal_year: int
    period: int
    document_no: str
    line_item: str
    posting_date: str
    account: str
    cost_center: str
    currency: str
    amount: Decimal
    text: str

    @property
    def key(self) -> tuple:
        return (self.company_code, self.fiscal_year, self.document_no, self.line_item)

    def as_params(self, run_id: str) -> tuple:
        return (
            run_id, self.company_code, self.fiscal_year, self.period, self.document_no, self.line_item,
            self.posting_date, self.account, self.cost_center, self.currency, self.amount, self.text,
        )


class Rejected(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def clean(raw: dict[str, str]) -> CleanRow:
    """Return a typed row or raise Rejected(reason)."""
    for col in REQUIRED:
        if not (raw.get(col) or "").strip():
            raise Rejected(f"missing_{col}")

    company = raw["company_code"].strip()
    if company not in ENTITIES:
        raise Rejected("unknown_company")

    account = raw["account"].strip()
    if account not in ACCOUNTS:
        raise Rejected("unknown_account")

    try:
        posting = date.fromisoformat(raw["posting_date"].strip())
    except ValueError:
        raise Rejected("bad_posting_date") from None

    try:
        fiscal_year = int(raw["fiscal_year"])
        period = int(raw["period"])
    except ValueError:
        raise Rejected("bad_period") from None
    if not 1 <= period <= 12 or posting.year != fiscal_year or posting.month != period:
        raise Rejected("period_mismatch")

    try:
        amount = Decimal(raw["amount"].strip())
    except InvalidOperation:
        raise Rejected("bad_amount") from None
    if amount != amount.quantize(Decimal("0.01")):
        raise Rejected("bad_amount_precision")

    currency = (raw.get("currency") or "").strip()
    if currency not in CURRENCIES:
        raise Rejected("unknown_currency")

    return CleanRow(
        company_code=company,
        fiscal_year=fiscal_year,
        period=period,
        document_no=raw["document_no"].strip(),
        line_item=raw["line_item"].strip(),
        posting_date=posting.isoformat(),
        account=account,
        cost_center=(raw.get("cost_center") or "").strip(),
        currency=currency,
        amount=amount,
        text=(raw.get("text") or "").strip()[:128],
    )


def raw_line(raw: dict[str, str]) -> str:
    return ";".join(raw.get(c, "") or "" for c in EXTRACT_COLUMNS)
