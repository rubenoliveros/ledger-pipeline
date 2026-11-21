"""DDL for the staging (stg) and control (ctl) schemas."""

from __future__ import annotations

from ledger.db import Database

# Table definitions written once; types are mapped per dialect below.
TABLES: dict[str, list[tuple[str, str]]] = {
    "ctl.runs": [
        ("run_id", "ID"),
        ("source_file", "TEXT_256"),
        ("file_hash", "TEXT_64"),
        ("method", "TEXT_16"),
        ("status", "TEXT_16"),
        ("started_at", "TS"),
        ("finished_at", "TS_NULL"),
        ("rows_read", "INT_NULL"),
        ("rows_loaded", "INT_NULL"),
        ("rows_rejected", "INT_NULL"),
        ("load_seconds", "FLOAT_NULL"),
        ("total_seconds", "FLOAT_NULL"),
        ("error", "TEXT_MAX_NULL"),
    ],
    "ctl.rejects": [
        ("run_id", "ID"),
        ("line_no", "INT"),
        ("reason", "TEXT_64"),
        ("raw_line", "TEXT_MAX"),
    ],
    "stg.ledger": [
        ("run_id", "ID"),
        ("company_code", "TEXT_8"),
        ("fiscal_year", "INT"),
        ("period", "INT"),
        ("document_no", "TEXT_16"),
        ("line_item", "TEXT_8"),
        ("posting_date", "DATE"),
        ("account", "TEXT_8"),
        ("cost_center", "TEXT_8"),
        ("currency", "TEXT_3"),
        ("amount", "MONEY"),
        ("text", "TEXT_128"),
    ],
}

TYPES = {
    "sqlite": {
        "ID": "TEXT NOT NULL", "TEXT_3": "TEXT NOT NULL", "TEXT_8": "TEXT NOT NULL",
        "TEXT_16": "TEXT NOT NULL", "TEXT_64": "TEXT NOT NULL", "TEXT_128": "TEXT",
        "TEXT_256": "TEXT NOT NULL", "TEXT_MAX": "TEXT NOT NULL", "TEXT_MAX_NULL": "TEXT",
        "INT": "INTEGER NOT NULL", "INT_NULL": "INTEGER", "FLOAT_NULL": "REAL",
        "TS": "TEXT NOT NULL", "TS_NULL": "TEXT", "DATE": "TEXT NOT NULL", "MONEY": "NUMERIC NOT NULL",
    },
    "mssql": {
        "ID": "CHAR(36) NOT NULL", "TEXT_3": "CHAR(3) NOT NULL", "TEXT_8": "VARCHAR(8) NOT NULL",
        "TEXT_16": "VARCHAR(16) NOT NULL", "TEXT_64": "VARCHAR(64) NOT NULL", "TEXT_128": "NVARCHAR(128) NULL",
        "TEXT_256": "NVARCHAR(256) NOT NULL", "TEXT_MAX": "NVARCHAR(MAX) NOT NULL",
        "TEXT_MAX_NULL": "NVARCHAR(MAX) NULL", "INT": "INT NOT NULL", "INT_NULL": "INT NULL",
        "FLOAT_NULL": "FLOAT NULL", "TS": "DATETIME2 NOT NULL", "TS_NULL": "DATETIME2 NULL",
        "DATE": "DATE NOT NULL", "MONEY": "DECIMAL(18,2) NOT NULL",
    },
}

CONSTRAINTS = {
    "ctl.runs": "PRIMARY KEY (run_id)",
    # Business key: one row per ERP line item. Makes duplicate loads impossible.
    "stg.ledger": "PRIMARY KEY (company_code, fiscal_year, document_no, line_item)",
}

INDEXES = [
    ("ix_ledger_run", "stg.ledger", "run_id"),
    ("ix_ledger_rollup", "stg.ledger", "company_code, account, fiscal_year, period"),
    ("ix_rejects_run", "ctl.rejects", "run_id"),
    ("ix_runs_hash", "ctl.runs", "file_hash"),
]


def _create_table_sql(name: str, dialect: str) -> str:
    cols = [f"{col} {TYPES[dialect][kind]}" for col, kind in TABLES[name]]
    if name in CONSTRAINTS:
        cols.append(CONSTRAINTS[name])
    return f"CREATE TABLE {name} (\n  " + ",\n  ".join(cols) + "\n)"


def create_schema(db: Database) -> None:
    cur = db.cursor()
    if db.dialect == "mssql":
        for schema in ("stg", "ctl"):
            cur.execute(f"IF SCHEMA_ID('{schema}') IS NULL EXEC('CREATE SCHEMA {schema}')")
        for name in TABLES:
            cur.execute(f"IF OBJECT_ID('{name}', 'U') IS NULL {_create_table_sql(name, 'mssql')}")
        for ix, table, cols in INDEXES:
            cur.execute(
                f"IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = '{ix}' "
                f"AND object_id = OBJECT_ID('{table}')) CREATE INDEX {ix} ON {table} ({cols})"
            )
    else:
        for name in TABLES:
            cur.execute(_create_table_sql(name, "sqlite").replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1))
        for ix, table, cols in INDEXES:
            schema, tbl = table.split(".")
            cur.execute(f"CREATE INDEX IF NOT EXISTS {schema}.{ix} ON {tbl} ({cols})")
    db.commit()


def drop_schema(db: Database) -> None:
    cur = db.cursor()
    for name in reversed(list(TABLES)):
        if db.dialect == "mssql":
            cur.execute(f"IF OBJECT_ID('{name}', 'U') IS NOT NULL DROP TABLE {name}")
        else:
            cur.execute(f"DROP TABLE IF EXISTS {name}")
    db.commit()
