# behaviour_log_0003 — Dual language support (English / Chinese)

**Status:** Implemented. Every free-text field on `CorePersonality` and
`InnerStateSnapshot` (the two models rebuilt in `behaviour_log_0002.md`)
now has an `_en`/`_zh` pair. Migration applied and verified against the
running Docker Postgres.

## Decision

All content — every field described in `behaviour_log_0002.md` as part of
Core Personality or Inner State — needs an English and a Chinese version.
Two shapes were on the table:

1. A separate translations table, FK'd back to `CorePersonality`/
   `InnerStateSnapshot`.
2. Parallel `_en`/`_zh` columns on the same row.

**Chosen: (2), parallel columns.** Reasoning:

- `sample-logic.py` — the reference AI-generation implementation already in
  this repo — solves the identical problem the same way: one `ElementResult`
  row per generation event, with `chinese_json` and `english_json` as two
  columns on that same row, produced together by one call
  (`generate_bilingual_personalized_content`). Parallel columns let the
  eventual AI-generation code here map directly onto the schema instead of
  splitting a paired result across two joined rows.
- It matches the denormalization call already made for `colour_key` on
  `InnerStateSnapshot` (see `behaviour_log_0002.md`) — content read on every
  request shouldn't need a join to assemble.
- The "querying might be heavy" concern behind option 1 doesn't hold up at
  the Postgres storage level: text columns beyond ~2KB are TOASTed
  (stored out-of-line automatically), so a query that only selects the
  needed language's columns doesn't pay for the other language sitting
  unread in the same row. A join costs more than the extra columns do.
- Real cost, stated plainly: this hardcodes the language set at exactly 2.
  Matches the ask and matches `sample-logic.py`'s own assumption. If a 3rd
  language becomes real, a separate table (or a JSONB-per-field column)
  scales better — worth revisiting only if that becomes an actual
  requirement, not preemptively.

## What became bilingual, and what didn't

Only free text became `_en`/`_zh`. Numbers, scores, and lookup keys stayed
single-column — they're language-neutral or reference a static content
library (whose own localization, if ever needed, is a separate concern
from per-row user data).

**`CorePersonality`**: `title`, `subtitle`, `overview`,
`birthday_number_content`, `life_path_number_content`,
`talent_number_content`, `summary` all split. `birthday_number`,
`life_path_number`, `talent_number` (the numeric/compound-code values
themselves, not their narrative content), and the five colour-score
columns did not.

**`InnerStateSnapshot`**: `insight`, `reflection_question`, `reminder`,
`current_focus`, `friendly_advice`, `affirmation`, `summary` all split.
The 4 pillars (`emotional_energy`/`mental_clarity`/`inner_pressure`/
`grounding`) and `colour_key` (a lookup key into the static `COLOURS`
content dict, not text itself) did not.

## Scope boundary — flagging, not deciding

This pass covers exactly the two models `behaviour_log_0002.md` redefined.
It does **not** touch `InnerReading` (`narrative`/`insight`/
`reflection_question`/`title`/`subtitle`), `CheckInSession.summary`,
`RecommendationProfile` (`current_focus`/`summary`), or
`RecommendationItem` (`title`/`reason`) — all of which are also
user-facing generated text and would need the same `_en`/`_zh` treatment
if they're meant to be bilingual too. Left out because they weren't part
of the Core Personality/Inner State field lists this exercise has been
scoped to — say if they should be included in a follow-up pass.

## Migration

`alembic/versions/01aec548f3cc_bilingual_content_fields.py`,
`down_revision = "b6e1c87c0a6d"`. Same drop-and-recreate approach as the
prior migration, for the same reason (demo data only, no preservation
need) — and `recommendation_profiles`/`recommendation_items` had to be
dropped and recreated again too, since both FK into the two tables being
rebuilt.

## Verified

`alembic upgrade head` against the running Docker Postgres — clean, no
errors. `\d core_personalities` / `\d inner_state_snapshots` in `psql`
confirm every column present exactly as designed. A Python import smoke
check confirms both SQLAlchemy models map without error. `GET /health`
confirms the app container itself stays up (import-time only — the
services/endpoints that construct these models in the old shape, already
broken by `behaviour_log_0002.md`'s pass, remain broken here too; not back
in scope for this pass either).
