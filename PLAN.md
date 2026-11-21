# Plan: ledger-pipeline

## Goal
A working, very close copy of the production pipeline: SAP general ledger data in, rules and AI-assisted classification with human approval, an audited SQL load, and an Oracle FCCS data load out. It runs locally for free and in Azure on free offers for the demo.

## The production story it mirrors
- SAP ledger line items (FAGLL03, default layout) exported by an automation because IT could not schedule an SAP job.
- Python + SQL Server staging (`stg.*`) and audit (`ctl.*`), every record tracked by RunID, idempotent reruns.
- Three regions disagreed on classification rules; the agreed rules became SQL and classify 99.9% of about 170,000 lines a month.
- About 200 edge cases a month: an LLM suggests a class and a reason, a reviewer approves, the audit log keeps suggestion vs decision.
- Batch loading cut the load from 15 minutes to 42 seconds; the close went from 7 days to 30 minutes.
- Outputs: a dashboard for stakeholders and the Oracle FCCS/HFM load.

## Target architecture

```
 SAP side (simulated)          Azure (free offers)                          Oracle side (simulated)
 ┌──────────────────┐   ┌────────────────────────────────────────────┐   ┌────────────────────────┐
 │ FAGLL03-style     │──▶│ Blob "landing" ─▶ pipeline job ─▶ Azure SQL │──▶│ FCCS mock (REST API)   │
 │ export generator  │   │   stg.* ctl.* rules + LLM review queue      │   │ upload ▸ run rule ▸    │
 └──────────────────┘   │   Blob "outbound": FCCS load file           │   │ job status ▸ kickouts  │
                        └────────────────────────────────────────────┘   └────────────────────────┘
```

Every piece also runs locally (SQLite or SQL Server in Docker, local folder instead of Blob, mock on localhost), so CI and anyone cloning the repo never need an Azure account.

## Decisions (2026-11-21)
- **Azure:** deploy to Rubén's existing subscription (one resource group, budget alert, one-command teardown).
- **LLM:** Azure OpenAI for live demos, same as production; a fake client for tests and CI. Token cost for ~200 lines per demo run is expected to be cents; checked before the first run.
- **SAP extract:** the standard FAGLL03-style layout below.
- **Dashboard:** both, a Power BI file (screenshots in the README) and a small web dashboard served next to the demo.

## Build order
1. Phase 2 (SAP-style export + parser), so everything after it works on realistic data.
2. Phase 4 (FCCS mapping, load file, mock, client, reconciliation), runnable locally.
3. Phase 3 (rules + Azure OpenAI review loop + audit + accuracy report).
4. Phase 5 (Azure deployment), then Phase 6 (dashboards, GIF, docs).

## Phase 1: audited load core (done)
- [x] Staging and control schemas, RunID audit, `rows_read = rows_loaded + rows_rejected`
- [x] Validation with specific reject reasons; idempotent and forced reruns
- [x] Row vs batch vs fast benchmark (SQLite numbers in README; SQL Server in CI)
- [x] 19 tests; CI on SQLite and SQL Server 2022
- [ ] First green CI run on GitHub; copy the SQL Server benchmark into the README

## Phase 2: realistic SAP data (the "SAP side")
We don't simulate SAP itself; we simulate what comes out of it: the file the automation downloads.

**Extract format: FAGLL03 spreadsheet/local-file export, default-style layout**
- Columns: Company Code, Fiscal Year, Period, Document Number, Line Item, Document Type, Posting Key, Document Date, Posting Date, G/L Account, Assignment, Business Area, Profit Center, Cost Center, Trading Partner, Tax Code, Amount in Local Currency, Local Currency, Clearing Document, Text.
- The quirks the real automation has to survive: a header block before the column row, separator lines, subtotal and total rows (`*`, `**`), European number format with trailing minus (`1.234,56-`), dates as `DD.MM.YYYY`, tab or `;` delimiters, Latin-1 encoding, one file per company code and period.

**Data realism (seeded generator, no external data)**
- Entities grouped in three regions (named Region A, B, C; no countries).
- Chart of accounts with SAP-style 6-8 digit numbers, plus master data files: accounts, cost/profit centers, entity-to-region.
- Document types and posting keys used consistently (SA journals, KR vendor invoices, DR customer invoices, AB clearing; keys 40/50, 31, 01).
- Real close patterns: month-end volume spikes, accruals reversed on day 1 of the next period, intercompany pairs that must match between two entities (Trading Partner), recurring entries, a few FX revaluation lines.
- Volume: about 170,000 lines a month across all entities; 12 periods available.
- Planted problems with a known answer key: unbalanced documents, unmapped accounts, intercompany mismatches, bad formats, duplicates, and about 200 lines a month whose class the rules can't decide.

**Parser**
- `ledger ingest` reads the raw export, drops header/subtotal rows, converts formats, maps columns, and hands clean rows to the Phase 1 load. Every dropped or fixed line is logged.

## Phase 3: classification and human review
- [ ] Rules as data: a `cfg.class_rules` table (account ranges, document types, cost centers, text patterns) with region overrides, versioned. Documents the "three regions, one agreed rule set" story.
- [ ] SQL classification in one set-based pass; target about 99.9% classified.
- [ ] Unclassified lines go to an LLM with structured output: fixed list of classes, required reason, confidence.
- [ ] Review queue (small web page or CLI): approve or correct; nothing loads to FCCS until approved.
- [ ] Audit table: suggestion, reason, reviewer decision, prompt version, model, tokens, latency, cost.
- [ ] Accuracy report per class and per prompt version, from the answer key and from reviewer decisions.
- [ ] A fake LLM client by default so tests and CI never call a paid API.

## Phase 4: Oracle FCCS (simulated)
**Mapping**
- SAP account to FCCS account, company code to FCCS entity, trading partner to Intercompany member (or `FCCS_No Intercompany`), plus fixed members: Scenario `Actual`, View `FCCS_Periodic`, Consolidation `FCCS_Entity Input`, Currency `Entity Currency`, Data Source `FCCS_Managed Data`, Multi-GAAP `FCCS_Local GAAP`, Movement by account type.
- Mapping tables are data files, versioned; unmapped members stop the load with a clear list.

**Load file**
- Two formats, both documented by Oracle: the Data Management/Data Integration flat file (one column per dimension plus Amount) and the native FCCS import format (Period, value, Point-of-View, cube).

**FCCS mock service (FastAPI)**
- Mirrors the EPM Cloud REST flow the real client would call:
  - Upload to inbox: `POST /interop/rest/11.1.2.3.600/applicationsnapshots/{file}/contents?extDirPath=inbox`
  - Run the integration: `POST /aif/rest/V1/jobs` with job type `INTEGRATION` (or the older `DATARULE`), periods and import/export mode
  - Poll the job: status `-1` running, `0` success, `1` error; text status RUNNING / SUCCESS / FAILED; log file name
- Holds a small metadata set (entities, accounts, intercompany members) and rejects lines with unknown members as "kickouts" in the job log, like the real tool.
- Stores loaded balances so a reconciliation can compare SQL totals vs "FCCS" totals per entity/account/period.

**Client**
- `fccs_client.py`: upload, run, poll with backoff, download log. Same code works against the mock or a real EPM instance by changing the base URL and credentials.

## Phase 5: Azure deployment (free offers)
- **Azure SQL Database, free offer:** 100,000 vCore seconds, 32 GB data and 32 GB backup per database per month, up to 10 databases per subscription; serverless with auto-pause so it uses no compute while idle.
- **Blob Storage:** `landing/` for SAP extracts, `outbound/` for FCCS files, `logs/`.
- **Pipeline job:** Azure Container Apps job or Azure Functions (both have monthly free grants); runs ingest, classify, load, export.
- **FCCS mock:** App Service free tier or the same Container Apps environment.
- **Infrastructure as code:** Bicep templates, one `deploy` and one `teardown` script, GitHub Actions deploy with OIDC (no stored secrets).
- **Cost guardrails:** budget alert at a few dollars, auto-pause on, free-amount-remaining alert on the database, everything in one resource group so teardown is one command.
- **Demo recording:** extract dropped in Blob, job runs, review queue, FCCS mock job succeeds, reconciliation shows zero difference.

## Phase 6: reporting and polish
- [ ] Power BI Desktop report (`.pbix`) on the SQL database: run history, rows by class, rejects by reason, LLM accuracy vs reviewer, reconciliation status. Screenshots in the README.
- [ ] Web dashboard with the same views, served by the demo app so anyone can open it.
- [ ] Architecture diagram, demo GIF, "design decisions" section (why staging, why RunID, why human approval, why batch).

## Done when
- One command runs the whole flow locally: generate SAP export, ingest, classify, review (auto-approve in demo mode), load, export, push to the FCCS mock, reconcile.
- CI is green on SQLite and SQL Server.
- The Azure deployment works from a clean subscription with `deploy`, and `teardown` removes everything.

## Out of scope
Real SAP or Oracle systems, real client rules or data, Power Automate flows (licensing), production security hardening beyond the demo.
