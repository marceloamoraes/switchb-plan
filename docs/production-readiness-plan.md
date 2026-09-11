# Production Readiness Plan

End-to-end checklist to take the pipeline in [`pipeline/`](../pipeline) from scaffold
to production. Estimates assume one engineer working solo with moderate GCP
familiarity. Ranges are wide because two things are unknown until you look at the
real corpus: the share of scanned/legacy `.doc`/`.xls` files (the slow processing
path) and your org's IAM/billing approval turnaround.

| # | Phase | Key actions | Estimate | Status |
|---|-------|-------------|----------|--------|
| 0 | **Write this plan** | Capture the end-to-end plan as a tracked doc before starting infra/code work | 0.5 hr | Done |
| 1 | **Project setup** | Enable APIs (Storage, Pub/Sub, Cloud Run, Vertex AI, BigQuery, Cloud Build), create least-privilege service accounts (not Owner/Editor), set budget alerts | 0.5–1 day | Not started |
| 2 | **Infra provisioning** | Run `infra/setup.sh` end to end in a real project: bucket + lifecycle rule, Pub/Sub topics/subscriptions, GCS notification, BigQuery dataset/table | 0.5–1 day | Not started |
| 3 | **Unit tests (new code)** | Write a pytest suite for `parsers.py` (one fixture file per extension incl. a scanned PDF and a legacy `.doc`) and `matcher.py` regex (true/false positive edge cases). No tests exist yet | 1–2 days | Not started |
| 4 | **Production-readiness fixes (new code)** | Two gaps in the current scaffold: (a) **idempotency** — Pub/Sub is at-least-once, so a redelivered message double-inserts into BigQuery; needs a dedup key (object generation) or `MERGE` instead of `insert_rows_json`. (b) **dead-letter queue** — add `--dead-letter-topic` + max delivery attempts to both subscriptions so a poison file doesn't retry forever | 1–1.5 days | Not started |
| 5 | **Phase 1 integration test** | Deploy to a staging Cloud Run service, push ~30–50 real sample files covering all 6 extensions + scanned PDFs, verify archive/extracted routing, test a corrupt/oversized file, confirm the Cloud Run timeout covers LibreOffice conversion + OCR | 1–2 days | Not started |
| 6 | **Phase 2 integration test** | Deploy staging service, validate Gemini structured output against the schema on real matched text, confirm BigQuery rows land correctly, measure actual $/doc | 1 day | Not started |
| 7 | **Data-quality pass** | Run the full pipeline against a few hundred to ~1,000 real files; spot-check precision/recall on key fields (Ampacity, Voltage, Vendor) and on the keyword filter itself (false negatives = missed switchgear docs, false positives = wasted AI spend). Tune regex/prompt based on findings | 1–2 days | Not started |
| 8 | **Observability & alerting** | Cloud Monitoring dashboards (Cloud Run errors/latency, Pub/Sub backlog, BQ row count), alert policy on error rate and DLQ depth | 0.5 day | Not started |
| 9 | **Security review** | Confirm both Cloud Run services are `--no-allow-unauthenticated`, Pub/Sub push uses OIDC (already in the script), IAM bindings are scoped per-service, no bucket is public | 0.5 day | Not started |
| 10 | **Full 130k backfill** | Kick off ingestion, monitor. Active engineering time is low, but wall-clock run time depends heavily on the legacy/scanned-doc mix — OCR and LibreOffice conversion are the slow paths. Ballpark: 4 hours to ~2 days of processing time with reasonable Cloud Run concurrency | 0.5 day active + up to 2 days passive | Not started |
| 11 | **Post-run QA & handoff** | Reprocess DLQ failures, validate final BigQuery count against expected match rate, spot-check a random sample, write runbook notes | 0.5–1 day | Not started |

**Total active engineering time: ~8–13 days**, likely spread across **2–4 calendar
weeks** once the backfill's passive wall-clock time and any IAM/billing approval
delays are factored in.

## Biggest unknowns

- Share of legacy `.doc`/`.xls` files (needs LibreOffice conversion, slower).
- Share of scanned-image files (needs OCR, slowest path).
- Actual keyword match rate — drives Phase 2 AI cost and how much data-quality
  tuning step 7 needs.

## Next step

Steps 3 and 4 are code, not process — they're the next thing to implement once this
plan is agreed on.
