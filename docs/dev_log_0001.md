# dev_log_0001 — Users, auth, and everything except AI

**Status:** Implemented and verified end-to-end against a running
`docker compose` stack. Companion to `api-endpoints-draft.md` and
`database-models-draft.md` — this is what actually got built from those
drafts, plus where it deliberately deviates.

## Scope of this pass

Built for real: users, auth (JWT), onboarding (birthdate → Core Personality),
recalibration (the A/B quiz), numerology, colour breakdown, subscription,
progress/gamification (XP, streak, garden, badges, rewards), journal, and the
colour catalog.

Built as **demo endpoints with real caching infrastructure, placeholder
content**: check-in and Inner Reading question generation.

Built as **real snapshotting, stubbed source data**: product recommendations
(no products table — see below).

Nothing here needed to change `api-endpoints-draft.md`'s or
`database-models-draft.md`'s open questions to be *resolved* first; I made
one concrete call per question (listed under "Decisions made", below) so
there was something running to look at, rather than leaving everything
blocked on a review cycle.

## How to verify it yourself

```bash
docker compose up -d --build
docker compose exec app alembic upgrade head   # only needed once, already applied
curl http://localhost:8010/docs                 # Swagger UI — every endpoint, try-it-out included
```

Or drive it directly: `POST /api/v1/auth/register` → grab `access_token` →
`Authorization: Bearer <token>` on everything else. A realistic path:
`register` → `POST /personality/onboarding {birthdate}` →
`POST /onboarding/complete` → `GET /check-ins/questions` →
`POST /check-ins` → `GET /inner-readings/questions` →
`POST /inner-readings` → `GET /recommendations/latest` → `GET /progress`.
I ran exactly this path (plus journal, rewards, colours, and the free-plan
gates) against the live container while building this — see "What I actually
tested" below, not just what compiles.

## The demo question-generation system (check-ins + Inner Reading)

This was the specific piece asked for: **the caching/reuse mechanism is
real**, only the "AI-generated" content inside it is a placeholder.

- **Check-ins are keyed by calendar date.** `GET /check-ins/questions` looks
  up `check_in_question_sets` for today; first request of the day inserts a
  row (currently static phrasing, one question per pillar), every later
  request *that same day, from any user* returns that same row.
- **Inner Readings are keyed by ordinal, not date**, per spec: `ordinal` is
  "this is user X's Nth reading," and the row in
  `inner_reading_question_sets` is shared by *everyone's* Nth reading,
  regardless of what date each person's Nth reading happens to land on.
  `GET /inner-readings/questions` computes the caller's next ordinal
  (`count(their past readings) + 1`) and get-or-generates that ordinal's row.
- Verified this isn't just "returns the same static JSON regardless" —
  confirmed via direct DB queries that a second, *different* user's request
  on the same day reuses the exact same `check_in_question_sets` row (count
  stayed at 1), and that ordinal 1's reading question set is one row shared
  across users too.
- Swapping placeholder generation for real AI later is a one-line change:
  `_generate_checkin_questions()` / `_generate_reading_questions()` in
  `app/services/questions.py` are the only two functions that would call out
  to an AI. Everything around them (the cache lookup, the insert-if-missing,
  the reuse) doesn't need to change.
- **Submission is real, not demo**: `POST /check-ins` and
  `POST /inner-readings` do the actual normalization → dimension-averaging →
  inner-state-snapshot → XP/streak/garden/badge/reward → recommendation
  cascade (ported from the frontend's `lib/scoring.ts` /
  `lib/gamification.ts` — this was never "AI" there either, it's rule-based
  math). Only the *questions themselves* are placeholder content; what
  happens once you answer them is fully implemented.

## Recommendations — no products table, real snapshots

Per spec: products aren't stored here. `app/services/recommendation.py`'s
`_fetch_products_stub()` is a clearly-marked placeholder for the eventual
third-party ecommerce API call — swap that one function out later and
nothing downstream changes. The focus→colour→routine matching around it is a
direct port of the frontend's `lib/recommendation.ts`, which — like the
question banks — was already rule-based, not real AI either.

What *is* real: every check-in and every Inner Reading creates a genuine
`recommendation_profiles` row (+ its `recommendation_items` children),
snapshotting that moment's colour/routine/product matches permanently. That
was the actual ask — "recommendations should be snapshotted for each inner
reading" — and it's not contingent on the AI/product-API pieces existing
yet.

Per "we need 1 endpoint that gets recommendation": there's exactly one —
`GET /recommendations/latest`. The history *exists* in the DB (every past
profile is still there, e.g. for a future "Your colour history" feature) but
isn't exposed via its own list endpoint yet, on purpose.

## Decisions made (resolving the drafts' open questions, one way each)

| Question (from the draft docs) | What I built |
|---|---|
| Polymorphic `source_id` | Two nullable FK columns + a `CHECK` constraint (exactly one set) — chose the option I'd recommended, on both `inner_state_snapshots` and `recommendation_profiles`. |
| Merge check-in/reading answer tables? | Kept separate (`check_in_answers`, `inner_reading_answers`) — simpler for now. |
| `primary_colour`: hex or FK? | Neither exactly — `recommendation_profiles.colour_key` (a string key into the Python `COLOURS` constant, since colours aren't a DB table; see next row). Response layer resolves name/swatch from the constant. |
| Catalog tables vs. app constants | Went further than the draft's split: colours, archetypes, badges, and rewards are **all** Python constants (`app/services/content.py`), not DB tables — only per-user *state* referencing them (`user_badges`, `user_rewards`) is a real table. Simpler and faster to build; trivially promotable to real tables later if admin-editability is ever needed. |
| `garden_progress` history | Confirmed no history — one row per user, overwritten weekly, exactly as scoped. |
| "Login quest" mechanism | **Not implemented.** No endpoint marks `LOGIN` complete anywhere. This is a real gap, not an oversight — needs a product decision (implicit-per-request vs. explicit ping) before it's worth building either way. |

## Other scope trims worth knowing about

- **No forgot/reset-password.** The endpoints doc flagged the original
  mock's reset flow (email + new password, no verification token) as
  something to *not* port as-is — I didn't build a replacement token-based
  flow either, since that's a real feature (email delivery, token storage)
  on its own, not something to improvise inside this pass.
- **No `/auth/logout`.** JWTs are stateless here; there's nothing server-side
  to invalidate yet. Add a blacklist table if that's ever needed.
- **Numerology isn't a verified port.** `app/services/numerology.py` is a
  standard-numerology implementation (digit-sum reduction, master numbers
  11/22/33), not a byte-for-byte copy of the frontend's
  `lifePathNumber`/`birthdayNumber`/`talentNumber` — I didn't have that
  source open while writing this. Concept and contract match
  ("deterministic from birthdate"); exact numbers for a given birthdate may
  not match what the frontend currently shows. Flagging so nobody's
  surprised by a mismatch later.
- **Insight/headline content is trimmed.** The frontend has 2 phrasing
  variants per focus for reading insights/titles; the backend has 1 each
  (`app/services/content.py`) to keep this pass's size sane. Same mechanism
  (seeded pick by focus key), just a smaller pool — add more variants
  whenever, it's a content change, not a structural one.
- **"Today" is UTC**, not the user's own timezone (`User.timezone` exists on
  the model but nothing reads it yet). Matters for streak/quest/garden logic
  near a day boundary — noted, not fixed.
- **`/catalog/products`, `/catalog/badges`, `/catalog/archetypes` from the
  endpoints draft don't exist as their own routes.** That content is used
  internally (recommendations, progress, personality responses) but nothing
  today needs to list it wholesale the way `/colours` does for the Colour
  Psychology page. Easy to add if a frontend screen needs it.

## What I actually tested

Not just "it imports" — ran a full flow against the live container and read
the responses:

1. Register → JWT issued, `/me` returns the new account.
2. `POST /personality/onboarding` with a birthdate → deterministic archetype
   (`quiet_strategist`), pillar scores, icon; confirmed same birthdate would
   reproduce the same result (it's a pure function, not re-rolled).
3. `/personality/numerology`, `/personality/colour-breakdown` — both require
   a birthdate on file and return plausible, deterministic values.
4. Check-in: fetched questions, submitted answers, got `xp_awarded: 10`.
5. Inner Reading: fetched (ordinal 1) questions, submitted, got a real
   narrative/insight/title generated from the actual answers, `xp_awarded:
   25`, and a `first_insight` badge newly earned.
6. `GET /state-snapshots/latest` reflected the reading's numbers correctly
   (balance math checked by hand: `(38+25+(100-75)+25)/4 = 28`, matches).
7. `/state-snapshots/trend?period=weekly` — today populated, every other day
   `null` (nothing to forward-fill from yet) — correct for a brand-new
   account. `period=monthly` correctly `403`s on the Free plan.
8. `/recommendations/latest` — colour matched the reading's focus
   ("Finding clarity" → Ocean), exactly 1 product returned (Free-plan limit).
9. `/progress` — XP total, streak, garden stage, today's quests, and the
   badge list all reflected steps 4–5 correctly.
10. Journal create + insights, rewards list (correctly all `LOCKED` — none
    of the thresholds were met yet), colours catalog — all returned
    sensible data.
11. **Gating, explicitly**: a second Inner Reading on the same (Free)
    account correctly `403`s with "Repeat Inner Readings require Premium."
12. **Reuse, explicitly**: registered a second, unrelated user and called
    `GET /check-ins/questions` — got byte-identical output to the first
    user's, and confirmed via `SELECT count(*) ... WHERE date = CURRENT_DATE`
    that it's still exactly one row, not two.
13. `GET /openapi.json` parses clean with all 31 routes — every Pydantic
    schema is well-formed, not just the ones I manually curled.

No console/server errors in `docker compose logs app` across any of this.
