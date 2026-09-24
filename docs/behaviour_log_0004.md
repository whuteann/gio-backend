# behaviour_log_0004 — Core Personality generation: service & endpoints

**Status:** Implemented, structurally verified (migrations applied,
imports clean, endpoints registered, deterministic numerology unit-checked
against `sample-logic.py`'s own worked example). No live OpenAI call made —
by explicit agreement, the first real end-to-end test is the user's to run.

## What this builds

Real generation logic for `CorePersonality` (previously just a model shape
per `behaviour_log_0002.md`/`0003.md`, nothing populated it). Same "numbers
in code, narrative from the model" principle as `sample-logic.py` and
`behaviour_log_0001.md`: every numeric value is computed deterministically
first and handed to the AI as a fixed fact it's told not to recalculate.

## Numerology (`app/services/numerology.py`, new functions)

Ported from `sample-logic.py`'s methodology, richer than the simplified
`life_path_number`/`birthday_number`/`talent_number` already in this file
(which stay untouched — they serve the separate, existing
`/personality/numerology` endpoint):

- `calculate_birthday_number` / `calculate_life_path_number` — day-of-month
  and year+month+day-summed respectively, reduced to a single digit with
  master numbers (11/22/33) preserved.
- `calculate_talent_number` — the `"XX/N"` compound string (e.g. `"38/2"`)
  from summing all 8 date digits then reducing.
- `calculate_colour_weights` — the digit-frequency weighting algorithm from
  `sample-logic.py`'s Five Elements analysis, migrated to Gio's 5 colours.
  Confirmed mapping: **Forest↔Wood(1,2), Scarlet↔Fire(3,4),
  Russet↔Earth(5,6), Gold↔Metal(7,8), Ocean↔Water(9,0)** — chosen to match
  each colour's existing static personality in `content.py::COLOURS`
  (Scarlet is already "vitality/passion", the Fire archetype; Ocean is
  already "calm/clarity", the Water archetype; etc.). Weight = `round(30 *
  count / total)`, clamped `[0, 30]`, same formula as the reference.

Verified against `sample-logic.py`'s own docstring example: `1992-07-28` →
talent number `"38/2"` — matches exactly.

## AI generation (`app/services/ai_personality.py`, new)

`generate_core_personality_content()` — one `AsyncOpenAI.responses.parse`
call against `CorePersonalityGeneration` (`app/schemas/ai_personality.py`:
`title`, `subtitle`, `overview`, the three `*_number_content` fields, and
`summary`). **Single language per call**, unlike `sample-logic.py`'s
bilingual schema — this is what makes the sequential generation flow
possible (below). The prompt hands the model the birthdate, all three
numbers, and all five colour weights as fixed facts with an explicit
"do not recalculate" instruction. No weight-override safety net is needed
here (unlike `sample-logic.py`): the model is never asked to output colour
weights at all, so there's nothing for it to get wrong.

`app/config.py` gained `openai_api_key`/`openai_model` (previously in
`.env` but silently dropped — `Settings` didn't declare them);
`docker-compose.yaml`'s `app` service now passes both through, same fix
class as the `CORS_ORIGINS` gap in `dev_log_0001.md`. `openai` added to
`requirements.txt`, image rebuilt.

## Sequential dual-language generation

Per direction: generate the requested language, return, generate the other
language afterward — not both before responding. `CorePersonality` gained
two bookkeeping columns to support this: `primary_language` (what
`/calculate` was called with) and `generation_status`
(`PARTIAL` → `READY`).

`POST /core-personality/calculate` generates and persists the requested
language synchronously, commits, then schedules the other language via
FastAPI `BackgroundTasks` — runs after the response is sent, in its own
short-lived DB session (`SessionLocal()` directly, not the request's
injected session, which is already closed by the time the background task
runs). `GET /core-personality/{id}/results` exposes `generation_status` so
the client knows whether to keep polling rather than having to infer it
from which columns happen to be null.

## Endpoints

- `POST /core-personality/calculate` — `{date_of_birth, language="en"}`,
  authenticated. 409 if a `CorePersonality` already exists for this user
  (matches the existing `POST /personality/onboarding` conflict
  convention — regenerating/recalibrating is explicitly separate future
  work, not this pass).
- `GET /core-personality/{id}/results` — authenticated, 404 if not found
  *or* the row belongs to a different user (never leak by id guessing).

## Explicitly out of scope (per direction)

Colour breakdown trait content (the Positive/Negative bullet lists in the
screenshot) stays hardcoded in `content.py::COLOURS` — shared static
content, not regenerated per user. This pass only adds the per-user numeric
`*_score` columns; nothing about the static trait copy changed.

## Verified

`alembic upgrade head` (two migrations: bilingual field additions already
covered in `behaviour_log_0003.md`, plus this pass's `primary_language`/
`generation_status` columns) — clean, confirmed via `psql`. Docker image
rebuilt for the new `openai` dependency, container healthy, no import
errors in logs. `GET /openapi.json` confirms both endpoints registered.
Numerology functions unit-checked directly (no API call) against
`sample-logic.py`'s own worked example — exact match, including master-
number preservation. **Not verified**: an actual `POST /calculate` round
trip against the live OpenAI API — deliberately left to the user, since
it spends real quota against the key in `.env`.
