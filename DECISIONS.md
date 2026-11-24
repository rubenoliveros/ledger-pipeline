# Decisions

## 2026-11-24: plan review

A structured review of the plan, one decision at a time. Each entry is the question and the answer Rubén chose; reasons are noted where he gave them.

### Classification and learning

1. **What gets classified.** Each ledger line gets a reporting category, about 12 to 15 classes, and the same list drives the FCCS account mapping.
2. **Learning from reviews.** Approvals do not become rules directly. They are stored as examples, and a rule is only suggested once there is enough consistent evidence for the same type of transaction.
3. **Same type of transaction.** Examples are grouped by G/L account, document type and a keyword from the line text.
4. **When a rule is suggested.** At least 5 reviewed examples across at least 2 months, all with the same final class and no disagreement.
5. **Examples in the prompt.** The closest reviewed examples, up to 5, are shown to the model with each new line. The accuracy report compares prompt versions with and without them.
6. **Confirming a rule candidate.** Candidates appear on a "Rule candidates" tab. A person confirms or rejects them. A confirmed rule becomes a new version in the rules table, linked to its evidence, and applies from the next run; closed periods are never rewritten.
7. **Three regions.** The data plants 4 documented disagreements between regions, resolved into one agreed rule set plus the few region overrides everyone accepted.
8. **Keyword source.** A fixed keyword list matched in the line text; lines with no match are grouped as "no keyword".

### The close

9. **Monthly cycle.** One SAP export per period, loaded month by month, with three months of demo data by default.
10. **Load gate.** The FCCS load for a period waits until every line is classified and reviewed. A demo switch auto-approves AI suggestions so the flow can run end to end.
11. **Reconciliation.** FCCS mock totals must match SQL totals to the cent for every entity, account and period; any difference fails the run and is listed cell by cell.
12. **Review screen.** A web page only, no Teams integration.

### Cost: zero, no Azure for now

13. **Budget.** The project must not cost anything. Azure is out for now; everything runs locally and on GitHub.
14. **AI.** A free local model provides suggestions. The model is chosen by an accuracy test of two or three small open models against the answer key. The repo ships pre-computed suggestions, so running the model is optional. The Azure OpenAI path stays in the code, switched off by a setting.
15. **File drop.** SAP files are uploaded through the web app into the database; a run starts from the upload or a button. Only free options.
16. **Plumbing.** Container images, if needed, go to GitHub's free registry. Logs go to the audit tables in the database.
17. **Local run.** `docker compose up` starts SQL Server, the web app with dashboard and review page, and the FCCS mock.
18. **Power BI.** Each run writes its reporting tables as CSV; the Power BI file reads them. A small web dashboard is part of the local app.
19. **Data size.** Full 170,000-line months locally and in CI.

### Public face

20. **Showcase.** A free GitHub Pages site with a recorded demo run: dashboards, screenshots of the review and rule-candidate pages, the reconciliation result and a short video.
21. **Contact form.** A Tally form, with responses sent to a Google Sheet. It asks for email and an unticked consent checkbox only, with a line that people can ask to have their data deleted.
22. **Where the form appears.** On the showcase, at the end of this README and in the GitHub profile README.

### Parked until free hosting or Azure returns

* Private sandbox per signed-in visitor: 7 days, max 10 new per day, 20,000 lines a month online.
* Email sign-in links, which need Rubén's own domain; he plans to buy one.
* Hosted landing page, admin access by email, CSV export of sign-ups.
* Azure SQL free offer set to pause instead of bill, AI budget cap, kill switch, "demo paused" fallback page with video.

### Open

* What the contact form offers: a live walkthrough call, updates on new projects, or both. Rubén will decide later.
