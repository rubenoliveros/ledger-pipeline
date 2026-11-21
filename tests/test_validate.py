import pytest

from ledger.validate import Rejected, clean

GOOD = {
    "company_code": "E110", "fiscal_year": "2026", "period": "03", "document_no": "1000123",
    "line_item": "001", "posting_date": "2026-03-14", "account": "6000", "cost_center": "CC010",
    "currency": "USD", "amount": "1250.40", "text": "test",
}


def test_good_row():
    row = clean(GOOD)
    assert row.period == 3 and str(row.amount) == "1250.40"


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("account", "", "missing_account"),
        ("account", "9999", "unknown_account"),
        ("company_code", "X1", "unknown_company"),
        ("posting_date", "2026-02-30", "bad_posting_date"),
        ("posting_date", "2026-04-01", "period_mismatch"),
        ("amount", "12,50", "bad_amount"),
        ("amount", "1.005", "bad_amount_precision"),
        ("currency", "GBP", "unknown_currency"),
    ],
)
def test_rejects(field, value, reason):
    with pytest.raises(Rejected) as exc:
        clean({**GOOD, field: value})
    assert exc.value.reason == reason
