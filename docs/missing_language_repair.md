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

The frontend refreshes data on language changes and labels fallback content
when the selected version is missing. That label does not claim a translation
is complete or that one will arrive automatically.
