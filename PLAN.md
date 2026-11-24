# Plan: ledger-pipeline

## Goal
A working, very close copy of the production pipeline: SAP general ledger data in, rules and AI-assisted classification with human approval, an audited SQL load, and an Oracle FCCS data load out. It runs locally at zero cost, and a static GitHub Pages showcase shows it working.

All decisions behind this plan, with their reasons, are in [DECISIONS.md](DECISIONS.md).

## The production story it mirrors
- SAP ledger line items (FAGLL03, default layout) exported by an automation because IT could not schedule an SAP job.
- Python + SQL Server staging (`stg.*`) and audit (`ctl.*`), every record tracked by RunID, idempotent reruns.
- Three regions disagreed on classification rules; the agreed rules became SQL and classify 99.9% of about 170,000 lines a month.
- About 200 edge cases a month: an LLM suggests a class and a reason, a reviewer approves, the audit log keeps suggestion vs decision.
- Batch loading cut the load from 15 minutes to 42 seconds; the close went from 7 days to 30 minutes.
- Outputs: a dashboard for stakeholders and the Oracle FCCS/HFM load.

## Target architecture (local, zero cost)

```
 SAP side (simulated)        docker compose: local stack                          Oracle side (simulated)
 ┌──────────────────┐   ┌───────────────────────────────────────────────┐   ┌────────────────────────┐
 │ FAGLL03-style     │──▶│ web app upload ─▶ pipeline ─▶ SQL Server       │──▶│ FCCS mock (REST API)   │
 │ export generator  │   │  stg.* ctl.* cfg.* rules, examples, review UI  │   │ upload ▸ run rule ▸    │
 └──────────────────┘   │  local model (optional) or pre-computed AI     │   │ job status ▸ kickouts  │
                        │  CSV exports ─▶ Power BI, web dashboard        │   └────────────────────────┘
                        └───────────────────────────────────────────────┘
 Public: GitHub Pages showcase (recorded demo run) + Tally contact form
```

## Build order
1. Phase 2: SAP-style export and parser, so everything after it works on realistic data.
2. Phase 4: FCCS mapping, load file, mock, client, reconciliation.
3. Phase 3: rules, examples, rule candidates, local model, review page.
4. Phase 5: dashboards, Power BI, GitHub Pages showcase, contact form.

## Phase 1: audited load core (done)
- [x] Staging and control schemas, RunID audit, `rows_read = rows_loaded + rows_rejected`
- [x] Validation with specific reject reasons; idempotent and forced reruns
- [x] Row vs batch vs fast benchmark (SQLite numbers in README; SQL Server in CI)
- [x] 19 tests; CI on SQLite and SQL Server 2022
- [x] First green CI run on GitHub; SQL Server benchmark in the README

## Phase 2: realistic SAP data (the "SAP side")
We don't simulate SAP itself; we simulate what comes out of it: the file the automation downloads.

**Extract format: FAGLL03 spreadsheet/local-file export, default-style layout**
- Columns: Company Code, Fiscal Year, Period, Document Number, Line Item, Document Type, Posting Key, Document Date, Posting Date, G/L Account, Assignment, Business Area, Profit Center, Cost Center, Trading Partner, Tax Code, Amount in Local Currency, Local Currency, Clearing Document, Text.
- Quirks the real automation has to survive: a header block before the column row, separator lines, subtotal and total rows (`*`, `**`), European number format with trailing minus (`1.234,56-`), dates as `DD.MM.YYYY`, tab or `;` delimiters, Latin-1 encoding, one file per company code and period.

**Data realism (seeded generator, no external data)**
- Entities grouped in three regions (Region A, B, C; no countries).
- SAP-style chart of accounts plus master data: accounts, cost/profit centers, entity-to-region.
- Document types and posting keys used consistently (SA, KR, DR, AB; keys 40/50, 31, 01).
- Close patterns: month-end spikes, accruals reversed on day 1 of the next period, intercompany pairs that must match, recurring entries, FX revaluation lines.
- About 170,000 lines a month; three months by default, 12 available.
- Answer key for planted problems: unbalanced documents, unmapped accounts, intercompany mismatches, bad formats, duplicates, and about 200 lines a month the rules can't classify. The answer key also holds the true class of every line.

**Parser**
- `ledger ingest` reads the raw export, drops header/subtotal rows, converts formats, maps columns and hands clean rows to the Phase 1 load. Every dropped or fixed line is logged.

## Phase 3: classification, examples and human review
- [ ] Reporting categories (12 to 15) as the class list; the same list drives FCCS account mapping.
- [ ] Rules as data in `cfg.class_rules`, versioned, with the few region overrides everyone accepted. `docs/regions.md` documents 4 planted disagreements and how they were resolved.
- [ ] SQL classification in one set-based pass; target about 99.9% classified.
- [ ] Unclassified lines go to the AI step: structured output, fixed class list, required reason, confidence. Up to 5 closest reviewed examples are included in each request.
- [ ] AI backends behind one interface: pre-computed suggestions file (default), local model through Ollama (optional), Azure OpenAI (in code, off), fake client for tests.
- [ ] Model choice: test two or three small open models against the answer key; the winner and the numbers go in the README.
- [ ] Review page: approve or correct each suggestion; nothing loads to FCCS for a period until its queue is empty. Demo switch auto-approves.
- [ ] Every reviewed line is stored as an example with its pattern key: G/L account + document type + keyword from a fixed list ("no keyword" when nothing matches).
- [ ] Rule candidates: a pattern with at least 5 examples over at least 2 months, all with the same class, appears on a "Rule candidates" tab. Confirmed candidates become a new rule version linked to their evidence and apply from the next run; closed periods are never rewritten.
- [ ] Audit table: suggestion, reason, reviewer decision, prompt version, model, latency.
- [ ] Accuracy report per class and per prompt version, with and without examples, against the answer key and reviewer decisions.

## Phase 4: Oracle FCCS (simulated)
**Mapping**
- Reporting class and SAP account to FCCS account, company code to FCCS entity, trading partner to Intercompany member (or `FCCS_No Intercompany`), plus fixed members: Scenario `Actual`, View `FCCS_Periodic`, Consolidation `FCCS_Entity Input`, Currency `Entity Currency`, Data Source `FCCS_Managed Data`, Multi-GAAP `FCCS_Local GAAP`, Movement by account type.
- Mapping tables are versioned data files; unmapped members stop the load with a clear list.

**Load file**
- The Data Management/Data Integration flat file and the native FCCS import format.

**FCCS mock service (FastAPI)**
- Mirrors the EPM Cloud REST flow: upload to inbox (`POST /interop/rest/11.1.2.3.600/applicationsnapshots/{file}/contents?extDirPath=inbox`), run the integration (`POST /aif/rest/V1/jobs`, job type `INTEGRATION` or `DATARULE`), poll the job (status `-1` running, `0` success, `1` error).
- Small metadata set; unknown members are rejected as kickouts in the job log.
- Stores loaded balances for reconciliation.

**Client and reconciliation**
- `fccs_client.py`: upload, run, poll with backoff, download log. Works against the mock or a real EPM instance by changing the base URL and credentials.
- Reconciliation: SQL totals vs FCCS mock totals per entity, account and period must match to the cent; any difference fails the run and is listed cell by cell.

## Phase 5: local stack, reporting and public showcase
- [ ] `docker compose up` starts SQL Server, the web app (upload, run button, dashboard, review page, rule candidates) and the FCCS mock.
- [ ] Uploads go straight into the database; a run starts from the upload or the button.
- [ ] Logs go to the `ctl.*` audit tables. Container images, if published, go to GitHub's free registry.
- [ ] Each run writes reporting tables as CSV: runs, rows by class, rejects by reason, AI accuracy, rule candidates, reconciliation.
- [ ] Power BI Desktop report (`.pbix`) reading the CSVs; screenshots in the README.
- [ ] Web dashboard with the same views inside the local app.
- [ ] GitHub Pages showcase: a recorded demo run with dashboards, review and rule-candidate screenshots, the reconciliation result and a short video.
- [ ] Tally contact form: email and an unticked consent checkbox only, with a line that people can ask to have their data deleted; responses go to a Google Sheet. Linked from the showcase, this README and the profile README. What the form offers is still open.
- [ ] Architecture diagram, demo GIF and a "design decisions" section in the README.

## Parked: hosted demo
Waits for free hosting or a return to Azure. Design already agreed (see DECISIONS.md):
- Private sandbox per signed-in visitor, 7 days, max 10 new per day, 20,000 lines a month.
- Email sign-in links from Rubén's own domain (to be bought).
- Hosted landing page, admin access by email, CSV export of sign-ups.
- Azure SQL free offer set to pause instead of bill, AI budget cap, kill switch, "demo paused" page with video.

## Done when
- `docker compose up` plus one command runs the whole flow locally: generate three SAP exports, ingest, classify, review (auto-approve in demo mode), load, export, push to the FCCS mock, reconcile.
- CI is green on SQLite and SQL Server.
- The GitHub Pages showcase is live with the recorded run and the contact form.
- Nothing in the project costs money.

## Out of scope
Real SAP or Oracle systems, real client rules or data, Power Automate flows (licensing), paid cloud services, production security hardening beyond the demo.
