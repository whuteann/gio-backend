# Repair missing language versions

Malay was added after some reading and personality results were saved. The
schema migration adds nullable columns; it does not generate content for old
rows. Those rows can still say READY from the earlier two-language release.
New background generation can also fail. Changing the UI language cannot fill
an empty database column.

`scripts/backfill_content_languages.py` checks actual generated fields rather
than trusting READY. It supports readings and personalities in en/zh/ms. The
old reading-only entry point delegates to this script and no longer imports the
removed `OTHER_LANGUAGE` constant.

Run on the backend host in the existing app container, after checking the
deployed revision and taking a database backup per deployment_runbook.md:

```bash
docker compose exec app python scripts/backfill_content_languages.py --language ms --dry-run --limit 5
```

Optionally add `--user-id <uuid>` to scope the inventory and repair to one
affected account. The output contains row IDs and counts, not personal text.

After reviewing the count, apply a small batch:

```bash
docker compose exec app python scripts/backfill_content_languages.py --language ms --limit 5 --apply --yes-production
```

Each incomplete body uses one call to the existing generation service and
therefore incurs model usage. Generation follows the current app rules; it
adds a language version, without recalculating scores or replacing existing
content. Matching curated insights/questions use their existing catalog copy.
Unknown historical catalog text is left untouched and may need manual review.
Existing focus/summary text outside the generated body is not regenerated.

Repairs commit one row at a time, re-check empty fields under a row lock after
generation, and never overwrite a version completed by a concurrent live task.
Failed rows roll back. Re-run dry-run to inspect the remainder before another
batch. Reload the affected dashboard and full result page with MS selected to
verify the populated Malay fields. Repeat with `--language zh` if older results
also lack Chinese.

`scripts/backfill_display_languages.py` separately inventories and translates
missing historical display fields: reading metadata, check-in titles, snapshot
messages, and recommendation copy. It defaults to dry-run; writes require
`--apply --yes-production`. Translation batches must return exactly the expected
keys. Existing English/Chinese and any already-populated Malay values are kept.

## Automatic recovery

Migration `d706da913b21` adds `content_language_jobs`, with a unique job for each
result/language. New personality calculations and readings enqueue their missing
versions; authenticated reads also recover a missed enqueue. Actual fields decide
readiness, so legacy READY flags do not conceal missing versions.

The application lifespan runs one worker per app process. PostgreSQL row locks
prevent duplicate claims across processes. Jobs get four attempts with delayed
retries; an interrupted worker's lease expires after ten minutes. A clean shutdown
requeues its active job. Exhausted jobs remain FAILED for diagnosis rather than
looping indefinitely. No prompts or generated text are stored in the job table.

The frontend refreshes on language changes and quietly polls pending selected
versions for up to five minutes, preserving the displayed page and unsaved drafts.
Fallback copy stays labelled until the selected version exists. Persistent outages
can still leave a version unavailable after all retries; inspect FAILED jobs.

For deployment, apply the additive migration from a staged checkout before
updating the live checkout; this keeps the old application working while the table
is created. No dependencies or compose changes are required. `LANGUAGE_WORKER_ENABLED`
defaults to true and can be disabled for isolated tests.

Integration tests require a disposable database whose name is exactly
`auren_language_qa`, and `AUREN_TEST_DATABASE=auren_language_qa`. They refuse a
production database, mock generation failures, and cover language switching,
new Malay results, duplicate enqueues, retries, leases, worker startup, and plan
limits in Malay. Keep real model smoke tests isolated from live user accounts.
