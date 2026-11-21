# Plan: ledger-pipeline

## Goal
Rebuild, with synthetic data, the ERP-to-consolidation ledger pipeline: staging and audit schemas in SQL Server, a reproducible load benchmark, and an LLM review loop for the rows SQL rules can't classify.

## Story it proves
"I moved 170,000 ledger rows a month from SAP to Oracle FCCS/HFM with staging, audit by RunID and idempotent reruns. Here is the same pattern, runnable, with synthetic data." Mirrors the production pattern (row-by-row 15 min vs batch 42 s); the demo publishes its own measured numbers.

## Phase 1: pipeline and benchmark (MVP)
- [x] uv project, pytest, CI workflow (SQLite tests + SQL Server 2022 service container)
- [ ] ruff lint in CI; commit `uv.lock`
- [x] `docker compose` with SQL Server Express
- [x] Synthetic generator: entities, accounts, periods, 170k rows, seeded so runs repeat
- [x] Schemas `stg.*` and `ctl.*` (runs: RunID, start, end, rows read/loaded/rejected, timings, errors)
- [x] Data quality checks with rejected rows kept and counted
- [x] Idempotent rerun: same file never duplicates rows; forced rerun supersedes the old run
- [x] Benchmark: row vs batch (SQLite, in README) and row vs batch vs `fast_executemany` (SQL Server, in CI summary)
- [ ] Copy the SQL Server benchmark from the first green CI run into the README; add a chart
- [x] Export in a consolidation-style flat file, with an unbalanced-documents check

## Phase 2: rule classification + LLM exception review
- [ ] SQL rule table classifies rows (config, not code)
- [ ] Unclassified rows go to an LLM with structured output: fixed class list + required reason
- [ ] Review queue (CLI or small web page): approve or correct each suggestion
- [ ] Audit table: suggestion, reason, reviewer decision, prompt version, cost, latency
- [ ] Eval report: accuracy vs a labeled set, by class and prompt version
- [ ] Works offline with a fake LLM client so CI never calls a paid API

## Phase 3: polish
- [ ] Architecture diagram, demo GIF
- [ ] "Design decisions" section: why staging, why RunID, why human approval

## Done when
`git clone`, `docker compose up -d`, `uv sync`, `uv run python -m ledger run` produces a loaded database, a `ctl.runs` row and a benchmark table; CI is green.

## Out of scope
Real SAP or Oracle connections, client rules, Power BI files.
