# ledger-pipeline

ERP-to-consolidation ledger pipeline rebuilt with synthetic data: 170k ledger rows loaded into SQL Server through staging and audit schemas, with a reproducible performance benchmark.

> Status: planning. Showcase: rebuilds a production pattern with synthetic data.

## Stack

Python, SQL Server Express (Docker), pytest, GitHub Actions.

## First version (MVP)

- [ ] Synthetic ledger generator (170k rows)
- [ ] Load into stg.* with a ctl.* audit table (RunID, row counts, timings)
- [ ] Benchmark: row-by-row vs bulk load

## Docs

Full spec (Spanish): [docs/SPEC.md](docs/SPEC.md)

## License

MIT
