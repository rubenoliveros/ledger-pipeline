"""Database access for SQLite (default, no install needed) and SQL Server (pyodbc).

Both backends expose the same two schemas so the pipeline SQL is identical:
  stg.*  staged ledger lines
  ctl.*  run audit: runs, rejects, step timings

SQLite has no CREATE SCHEMA, so each schema is an attached database file
(`<db>.stg.sqlite`, `<db>.ctl.sqlite`), which keeps `stg.ledger` style names working.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

# sqlite3 has no Decimal type; store the exact text and let NUMERIC affinity handle it.
sqlite3.register_adapter(Decimal, str)


@dataclass
class Database:
    url: str
    conn: object
    dialect: str  # "sqlite" | "mssql"

    def cursor(self):
        return self.conn.cursor()

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def scalar(self, sql: str, params: tuple = ()):
        cur = self.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return None if row is None else row[0]

    def rows(self, sql: str, params: tuple = ()) -> list[tuple]:
        cur = self.cursor()
        cur.execute(sql, params)
        return [tuple(r) for r in cur.fetchall()]


def connect(url: str) -> Database:
    """Open a database.

    sqlite:///path/to/ledger.db   file database (schemas attached next to it)
    sqlite:///:memory:            in-memory (tests)
    mssql://                      SQL Server; ODBC string from LEDGER_MSSQL_CONN
    """
    if url.startswith("sqlite:///"):
        target = url[len("sqlite:///"):]
        if target == ":memory:":
            conn = sqlite3.connect(":memory:")
            conn.execute("ATTACH DATABASE ':memory:' AS stg")
            conn.execute("ATTACH DATABASE ':memory:' AS ctl")
        else:
            base = Path(target)
            base.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(base)
            conn.execute("ATTACH DATABASE ? AS stg", (str(base.with_suffix(".stg.sqlite")),))
            conn.execute("ATTACH DATABASE ? AS ctl", (str(base.with_suffix(".ctl.sqlite")),))
        conn.execute("PRAGMA foreign_keys = ON")
        return Database(url, conn, "sqlite")

    if url.startswith("mssql://"):
        try:
            import pyodbc  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise SystemExit("SQL Server support needs the extra: uv sync --extra mssql") from exc
        odbc = os.environ.get("LEDGER_MSSQL_CONN")
        if not odbc:
            raise SystemExit("Set LEDGER_MSSQL_CONN to an ODBC connection string (see .env.example)")
        database = os.environ.get("LEDGER_MSSQL_DATABASE", "ledger")
        if not database.replace("_", "").isalnum():
            raise SystemExit("LEDGER_MSSQL_DATABASE must be letters, digits or underscores")
        conn = pyodbc.connect(odbc, autocommit=True)
        conn.cursor().execute(f"IF DB_ID('{database}') IS NULL CREATE DATABASE [{database}]")
        conn.cursor().execute(f"USE [{database}]")
        conn.autocommit = False
        return Database(url, conn, "mssql")

    raise SystemExit(f"Unsupported database URL: {url}")


@contextmanager
def opened(url: str):
    db = connect(url)
    try:
        yield db
    finally:
        db.close()
