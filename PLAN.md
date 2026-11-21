# Plan: ledger-pipeline

## Goal
Rebuild, with synthetic data, the ERP-to-consolidation ledger pipeline: staging and audit schemas in SQL Server, a reproducible load benchmark, and an LLM review loop for the rows SQL rules can't classify.

## Story it proves
"I moved 170,000 ledger rows a month from SAP to Oracle FCCS/HFM with staging, audit by RunID and idempotent reruns. Here is the same pattern, runnable, with synthetic data." Mirrors the production pattern (row-by-row 15 min vs batch 42 s); the demo publishes its own measured numbers.

## Phase 1: pipeline and benchmark (MVP)
- [ ] `uv init`, pytest, ruff, CI workflow with a SQL Server service container
- [ ] `docker compose` with SQL Server Express (or Azure SQL Edge on ARM)
- [ ] Synthetic generator: entities, accounts, periods, 170k rows, seeded so runs repeat
- [ ] Schemas `stg.*` (raw load) and `ctl.*` (runs: RunID, start, end, rows read/loaded/rejected, errors)
- [ ] Data quality checks with rejected rows kept and counted
- [ ] Idempotent rerun: same RunID input never duplicates rows
- [ ] Benchmark: row by row vs `fast_executemany` vs bulk insert; results table + chart in README
- [ ] Export in a consolidation-style flat file

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
