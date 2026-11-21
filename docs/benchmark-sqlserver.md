Backend: SQL Server 2022 (GitHub Actions service container, same host) · Python 3.14.4 · Linux x86_64 · CI run #2

| Method | Rows loaded | Load time (s) | Rows/s | Speed-up vs row |
|---|---:|---:|---:|---:|
| row | 49,850 | 21.96 | 2,270 | 1.0x |
| batch | 49,850 | 6.08 | 8,202 | 3.6x |
| fast | 49,850 | 1.18 | 42,103 | 18.6x |
