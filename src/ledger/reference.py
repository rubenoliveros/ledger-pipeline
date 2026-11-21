"""Synthetic reference data: entities and chart of accounts.

Nothing here comes from a real company. Ranges follow a common ERP layout
(1xxx assets, 2xxx liabilities, 3xxx equity, 4xxx revenue, 5xxx-6xxx expenses).
"""

from __future__ import annotations

ENTITIES: dict[str, str] = {
    "E100": "Holding",
    "E110": "North Operations",
    "E120": "South Operations",
    "E130": "Shared Services",
    "E140": "Distribution",
    "E150": "Manufacturing",
}

CURRENCIES = ("USD", "EUR")

ACCOUNTS: dict[str, tuple[str, str]] = {
    # account: (name, category)
    "1000": ("Cash and equivalents", "ASSET"),
    "1100": ("Accounts receivable", "ASSET"),
    "1200": ("Inventory", "ASSET"),
    "1500": ("Fixed assets", "ASSET"),
    "1900": ("Intercompany receivable", "ASSET"),
    "2000": ("Accounts payable", "LIABILITY"),
    "2100": ("Accrued liabilities", "LIABILITY"),
    "2900": ("Intercompany payable", "LIABILITY"),
    "3000": ("Retained earnings", "EQUITY"),
    "4000": ("Product revenue", "REVENUE"),
    "4100": ("Service revenue", "REVENUE"),
    "5000": ("Cost of goods sold", "EXPENSE"),
    "6000": ("Salaries", "EXPENSE"),
    "6100": ("Rent", "EXPENSE"),
    "6200": ("Travel", "EXPENSE"),
    "6300": ("Software and licenses", "EXPENSE"),
    "6900": ("Other operating expenses", "EXPENSE"),
}

COST_CENTERS = tuple(f"CC{n:03d}" for n in range(10, 60, 5))

# Columns of the extract, in file order (similar in spirit to an ERP line-item report).
EXTRACT_COLUMNS = (
    "company_code",
    "fiscal_year",
    "period",
    "document_no",
    "line_item",
    "posting_date",
    "account",
    "cost_center",
    "currency",
    "amount",
    "text",
)
