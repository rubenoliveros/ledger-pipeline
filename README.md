# ledger-pipeline

[![ci](https://github.com/rubenoliveros/ledger-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/rubenoliveros/ledger-pipeline/actions/workflows/ci.yml)

An audited ERP-to-consolidation ledger load: a ledger extract goes through validation into staging tables, every run is recorded with a RunID, reruns never duplicate data, and the result is rolled up into a consolidation data-load file.

> This project is very similar to a pipeline I built for production, which moves SAP ledger data into Oracle FCCS/HFM. Same architecture and design decisions; synthetic data and generic names.

## Why

Financial close depends on loading every ledger line exactly once, proving it, and doing it fast enough to rerun when something upstream changes. The production version of this pattern loads about 170,000 transactions a month; switching from row-by-row inserts to batch loading cut the load from 15 minutes to 42 seconds. This repo reproduces that pattern so it can be run, tested and measured by anyone.

## Run it

```bash
git clone https://github.com/rubenoliveros/ledger-pipeline.git && cd ledger-pipeline
uv sync
uv run ledger generate --rows 170000        # synthetic extract with ~0.3% known defects
uv run ledger run data/ledger_extract.csv   # validate + load, audited in ctl.*
uv run ledger export                        # consolidation load file in out/
uv run pytest
```

SQLite is the default backend, so no installation is needed. For SQL Server:

```bash
cp .env.example .env            # set a strong password
docker compose up -d
uv sync --extra mssql
uv run ledger run data/ledger_extract.csv --db mssql:// --method fast
```

## How it works

```mermaid
flowchart LR
    A[ERP extract<br/>CSV] --> B{Validate<br/>each line}
    B -- clean --> C[(stg.ledger)]
    B -- rejected + reason --> D[(ctl.rejects)]
    C --> E[Roll up by entity,<br/>account, period]
    E --> F[Consolidation<br/>load file]
    R[(ctl.runs<br/>RunID, counts, timings, status)] -.audits.- B
    R -.audits.- C
```

- **Two schemas with different jobs.** `stg.*` holds the data, `ctl.*` holds the evidence: one `ctl.runs` row per run (file hash, method, rows read/loaded/rejected, timings, status, error) and one `ctl.rejects` row per rejected line with its reason and the raw line.
- **Nothing disappears.** For every run, `rows_read = rows_loaded + rows_rejected`, and the tests check it.
- **Idempotent reruns.** The business key (company, fiscal year, document, line) is the primary key, so a line cannot load twice. Loading the same file again is skipped; a forced rerun replaces what the earlier run loaded. With the batch methods this happens in one transaction, so a failure rolls back to the last good state.
- **Overlapping extracts are safe.** Lines already loaded from another file are rejected as `key_already_loaded` instead of failing the whole load.
- **Rejects are specific.** Missing fields, unknown accounts or companies, impossible dates, posting dates outside the period, malformed amounts, duplicates. The export also counts journal entries that no longer net to zero, so a fix happens at the source instead of in the totals.
- **Load method is a setting.** `row` (one insert and one commit per line), `batch` (executemany in 5,000-row chunks, one commit), `fast` (SQL Server `fast_executemany`).

## Benchmark

Same 170,000-row extract, fresh database each time ([docs/benchmark-sqlite.md](docs/benchmark-sqlite.md)):

| Method | Rows loaded | Load time (s) | Rows/s | Speed-up vs row |
|---|---:|---:|---:|---:|
| row | 169,503 | 196.77 | 861 | 1.0x |
| batch | 169,503 | 0.96 | 176,934 | 205.4x |

CI also runs the pipeline and a row / batch / fast benchmark against SQL Server 2022; the table is published in each run's summary. Reproduce locally with `uv run ledger benchmark data/ledger_extract.csv`.

## Project layout

```
src/ledger/
  generate.py   synthetic extract with balanced journal entries and injected defects
  validate.py   line-level checks, typed rows, reject reasons
  schema.py     stg/ctl DDL for SQLite and SQL Server
  pipeline.py   audited, idempotent load
  export.py     consolidation roll-up and balance check
  benchmark.py  load method comparison
tests/          generator, validation, accounting of every row, reruns, rollback, export
```

## Next

Phase 2 (see [PLAN.md](PLAN.md)): SQL rules classify lines, the leftovers go to an LLM with a fixed set of classes and a required reason, a person approves or corrects each suggestion, and an evaluation report measures accuracy per prompt version.

## License

MIT
