# behaviour_log_0007 — Inner Reading: real generation & outcome

**Status:** Implemented and verified live (all 5 phases). All open
questions were resolved by taking this document's own recommendation in
each case — explicitly a first pass ("basic structure and logic," not
final tuning): see "How the open questions were resolved" below before
the original planning text, which is left intact underneath for context.

## How the open questions were resolved

1. **Pillar "weightage"** → equal-weight average, no special logic.
   `dimension_averages()` needed no change — verified live with 8-answer
   input across both pillars' 2 questions each.
2. **Where reading-specific content lives** → kept `InnerReading`'s own
   `narrative`/`insight`/`reflection_question`/`title`/`subtitle`/(new)
   `life_area_insights` columns, populated by the new AI outcome call.
   Chosen specifically to avoid frontend churn: `/inner-reading/[id]/result`
   and `/inner-reading/history` needed **zero changes** — confirmed via
   `gio-member-app`'s existing `InnerReadingOut` type already matching the
   new `life_area_insights` shape exactly. The six shared fields still also
   land on `InnerStateSnapshot` via the existing cascade (unchanged),
   same as check-in — so this isn't a fork, it's "both," not "either/or."
3. **`life_area_insights` → AI-generated** → confirmed, folded into the
   same outcome call as the other fields (`life_area_work`,
   `life_area_relationships`, `life_area_personal_growth`,
   `life_area_conflict_management`).
4. **Question depth framing** → confirmed as proposed: retrospective,
   multi-day framing ("Looking back over the last few days...",
   "Lately...", "This week..."). Verified live — real generated questions
   matched this framing and were meaningfully distinct within each pillar's
   pair.
5. **8-question schema shape** → confirmed as proposed: 8 named fields
   (`emotional_energy_1`/`_2`, etc.) on `InnerReadingQuestionSetGeneration`.

---

*Original planning text below, kept for context.*

## Starting point — what already exists

Inner Reading already has real endpoints and a real frontend
(`GET /inner-readings/questions`, `POST /inner-readings`,
`GET /inner-readings`, `GET /inner-readings/{id}`, all live and called from
`gio-member-app/lib/api/reflections.ts`; `/inner-reading/history` and
`/inner-reading/[id]/result` are already backend-wired per
`gio-member-app/docs/dev_log_0001.md`). What's still demo/static:

- **Questions**: `app/services/questions.py::get_or_generate_reading_question_set`
  returns 8 questions (2 per pillar, cycling `DEMO_READING_QUESTIONS`) —
  already the right *count*, but static text, and cached by a single
  global `ordinal` with no daily reset (`InnerReadingQuestionSet.ordinal`,
  `unique=True`).
- **Outcome**: `readings.py::submit_inner_reading` builds `narrative`,
  `insight`, `reflection_question`, `title`, `subtitle` from static
  libraries (`content.py::INSIGHT_LIBRARY`/`HEADLINE_LIBRARY`) keyed only
  by `resolve_focus_key()` — same handful of canned variants for every
  user who lands on that focus, and `life_area_insights`
  (`content.py::LIFE_AREA_INSIGHTS`, Premium-gated at read time via
  `reading_content_for_plan`) is the same static library, not generated.
- **Cascade**: `apply_reflection_side_effects` already accepts
  `inner_reading_id` and an optional `narrative_content` dict — Inner
  Reading currently passes `narrative_content=None` (explicit, documented
  in `cascade.py`'s own docstring as "Inner Reading passes None... same as
  before this pass"). No cascade.py change needed to wire real content
  through; the six-field plumbing already exists and is shared.
- **Narrative**: `NarrativeEntry`/`NarrativeProfile`
  (`behaviour_log_0005.md`) are already source-agnostic —
  `source_type="INNER_READING"` + `inner_reading_id` is already a valid
  row shape, just unused so far. No model change needed there either.

So this is narrower than `behaviour_log_0006.md` was: the shared
infrastructure (cascade, narrative memory, the six-field outcome shape) is
already built and generic. What's actually new is the same three things
check-in needed — real question generation, a daily-shared increment
cache, and real outcome generation — plus the reading-specific differences
called out below.

## The four stated differences from Emotional Check-In

1. **Question "depth"** — Inner Reading's existing static questions are
   already retrospective/reflective in framing ("Looking back on the last
   few days...", "What is the weight you've been quietly carrying this
   week?") versus check-in's present-moment framing ("...right now?").
   Proposed concrete definition for the AI prompt: longer time horizon
   (days, not "right now"), inviting a more considered answer, still a
   single sentence expecting a 1-5 rating — i.e. the same contract as
   check-in's prompt, with the framing instruction changed. Open to
   confirmation (see open questions).
2. **Number of questions (8)** — already correct today, just static.
   New question: does the AI generation schema need this as 8 explicit
   named fields (`emotional_energy_1`, `emotional_energy_2`, ... —
   doubling check-in's `CheckInQuestionSetGeneration` pattern) for the
   same structural guarantee (no list to validate, dimension is
   positional), or a validated list of 8 `{dimension, text}` items with a
   fixed-order constraint? **Recommendation: named fields**, consistent
   with check-in's own schema and this codebase's stated preference for
   letting the schema itself enforce shape rather than validating a list.
3. **Computed 4 pillars "weightage"** — genuinely unclear from the spec as
   given, flagged as the most important open question below rather than
   assumed. `dimension_averages()` already averages *all* answers sharing
   a `dimension` key with no change needed if "weightage" just means "2
   questions per pillar, averaged equally" (which is how it already
   behaves — check-in's Phase 3 hit exactly this "confirmed, no change
   needed" outcome). If something more deliberate is meant — e.g.
   weighting Inner Reading's result against the user's recent check-in
   history, or against the previous reading, rather than scoring this
   reading in isolation — that's a materially different, bigger piece of
   work and needs to be scoped explicitly before Phase 3 starts.
4. **"Generated Analysis"** — proposed mapping: `life_area_insights` (the
   existing Premium-gated work/relationships/personal_growth/
   conflict_management breakdown) moves from `content.py`'s static
   library to real AI generation, same depth-gating mechanism
   (`reading_content_for_plan`) staying in place. Open to confirmation —
   the spec doesn't name this field, but it's the only existing artifact
   that matches "a fuller generated analysis" beyond the six narrative
   fields shared with check-in.

## Phase 1 — Database models

- **`User`**: new `last_inner_reading_at` (`DateTime(timezone=True)`,
  nullable) + `inner_reading_count_today` (`Integer`, default `0`) —
  exact mirror of check-in's `last_check_in_at`/`check_in_count_today`,
  and explicitly **separate** from `inner_reading_weekly_count()`
  (`entitlement.py`, the free-vs-Premium weekly-limit counter, which
  stays as-is and untouched by this feature).
- **`InnerReadingQuestionSet`**: `ordinal` (`unique=True` global, no
  reset) → composite `(date, increment)`, exact mirror of
  `CheckInQuestionSet`'s Phase 1 change. `increment` here means "this
  user's 1st / 2nd / ... Inner Reading *of the day*," not lifetime
  ordinal — `InnerReading.ordinal` (lifetime count, used today for
  display/numbering) is unaffected and stays as-is.
- **`InnerReading`**: add `narrative_entry_id` FK → `narrative_entries.id`
  (nullable, `ondelete="SET NULL"`), exact mirror of
  `CheckInSession.narrative_entry_id`.
- **Open question, blocks this phase**: do `InnerReading.insight`,
  `.reflection_question`, `.narrative`, `.title`, `.subtitle` get
  consolidated onto `InnerStateSnapshot`'s six-field pattern (matching how
  check-in fully separated — `CheckInSession` carries only a deterministic
  `summary` label, all AI content lives on the snapshot), or do they stay
  as `InnerReading`'s own populated-by-AI columns? Consolidating is more
  consistent and avoids two places to update per outcome; keeping them
  avoids touching the existing frontend result page's field names
  (`reading.insight`, `reading.title`, etc. are already rendered directly
  from `InnerReadingOut`). Recommend resolving this alongside the
  `life_area_insights` question, since both are about where reading-
  specific generated content should live.
- Migration, additive/repointing only where the above is decided.

## Phase 2 — Question generation service

- New `InnerReadingQuestionSetGeneration` schema
  (`app/schemas/ai_questions.py`) — 8 named fields per difference #2
  above, same "no numbers, question text only" contract as check-in's.
- New `generate_reading_questions()` (`app/services/ai_questions.py`),
  prompt built around difference #1's depth/retrospection framing.
- `next_inner_reading_increment(user) -> int` — exact mirror of
  `next_check_in_increment`, reading the new `User` fields; pure
  calculation, persisted only at submit time (Phase 4), not at
  questions-fetch time — same reasoning as check-in's Phase 2.
- `get_or_generate_reading_question_set(db, on_date, increment)` rewritten
  to the `(date, increment)` keying + real AI call, replacing
  `_generate_reading_questions()`/`DEMO_READING_QUESTIONS`.
- `readings.py::get_questions` updated to call the new increment helper
  and the now-async generator (mirrors `checkins.py`'s Phase 2 update).
- Verification plan, mirroring check-in's Phase 2: confirm real generation
  (not static text), confirm same-day cross-user cache sharing at a given
  increment, confirm a second same-day reading gets its own separately-
  cached increment-2 set.

## Phase 3 — Results parsing

Blocked on open question 3 above (pillar "weightage"). If resolved as
"no change" (equal-weight average across 2 answers per pillar, same as
check-in's Phase 3 outcome): no code change, verify
`dimension_averages()`/`resolve_focus_key()` behave correctly on an
8-answer, 2-per-pillar input the same way Phase 3 of `behaviour_log_0006.md`
verified check-in's 4-answer input. If resolved as something more than
that: scope becomes its own sub-plan, not assumed here.

## Phase 4 — Outcome generation

- New `generate_reading_outcome()` — mirrors
  `ai_outcome.py::generate_checkin_outcome`'s shape (dims, focus label,
  last-5 `recent_narrative_summaries`, no `temperature`), reading-specific
  prompt framing per difference #1. Six narrative fields +
  `narrative_summary`, same as check-in's `CheckInOutcomeGeneration` —
  consider whether this warrants a shared base schema/prompt-builder given
  how close the two are, or two independent files matching
  `ai_questions.py`'s existing per-feature separation. Lean toward the
  latter for consistency with Phase 2, but worth a second look once
  written since the overlap here is larger than the questions side.
- If difference #4 is confirmed (AI-generated `life_area_insights`):
  extend this same generation call with 4 additional fields (one per life
  area) rather than a second round trip, matching how check-in's Phase 4
  folded `narrative_summary` into the same call as the six fields instead
  of a second call.
- **Inner State pillar update**: deterministic, via the existing
  `apply_reflection_side_effects` — no `cascade.py` change needed, just
  passing a real `narrative_content` dict instead of `None`.
- **New `NarrativeEntry`**: `source_type="INNER_READING"`,
  `inner_reading_id` set — same `create_narrative_entry` helper check-in
  already uses (`app/services/narrative.py`), no service change needed.
- `readings.py::submit_inner_reading` rewritten to compute
  `dims`/`focus_key`/`focus_label`, call `generate_reading_outcome`, pass
  `narrative_content` into `apply_reflection_side_effects`, create the
  `NarrativeEntry`, set `InnerReading.narrative_entry_id`, and (pending
  Phase 1's open question) either update `InnerReading`'s own content
  columns or stop populating them — mirrors `checkins.py::submit_check_in`'s
  Phase 4 shape closely.
- `User.last_inner_reading_at`/`.inner_reading_count_today` persisted here
  only, at submit time — same reasoning as check-in.

## Phase 5 — Endpoints

Likely little to nothing new, same outcome as check-in's Phase 5:

- `GET /inner-readings/questions`, `POST /inner-readings`,
  `GET /inner-readings`, `GET /inner-readings/{id}` already exist and
  already back the already-wired `/inner-reading/history` and
  `/inner-reading/[id]/result` frontend pages — per the spec's own
  "Accessible as an inner reading record history, and include details
  page," this is **already satisfied**, not new work.
- **Conditional on Phase 1's consolidation question**: if reading content
  moves onto `InnerStateSnapshot` (matching check-in's separation), the
  existing `InnerReadingOut`/`GET /inner-readings/{id}` response loses its
  `insight`/`reflection_question`/`narrative`/`title`/`subtitle` content,
  and a `GET /inner-readings/{id}/results`-style endpoint (mirroring the
  one just added for check-in, `CheckInResultsOut`) would be needed
  instead — with a corresponding frontend change to
  `/inner-reading/[id]/result` (currently reads those fields directly off
  `InnerReadingOut`). If those columns stay on `InnerReading` itself, no
  endpoint or frontend change is needed at all here.
- `/inner-reading` (hub) is unrelated, pre-existing, already-tracked
  scope: still on the old `AppStateContext` mock per
  `gio-member-app/docs/dev_log_0001.md`'s "Known gap" note. Not part of
  this feature; flagged only so it isn't mistaken for something this plan
  covers.

## Open questions

All five resolved — see "How the open questions were resolved" at the top
of this document.

## Implementation notes (what actually landed)

- **Models**: `User.last_inner_reading_at`/`.inner_reading_count_today`;
  `InnerReadingQuestionSet.ordinal` → `(date, increment)`
  (`uq_inner_reading_question_set_date_increment`); `InnerReading` gained
  `narrative_entry_id` (FK → `narrative_entries`, `SET NULL`) and
  `life_area_insights` (JSONB). Migration
  `alembic/versions/d9b5ce16447b_inner_reading_phase_1_models.py` —
  existing `inner_reading_question_sets` rows (4, all stale static-demo
  content) deleted rather than backfilled, since nothing about them was
  worth preserving under the new keying scheme.
- **`app/schemas/ai_questions.py::InnerReadingQuestionSetGeneration`** — 8
  named fields (`{dimension}_1`/`_2`). **`app/services/ai_questions.py`**
  gained `generate_reading_questions()` + `_READING_PROMPT` (retrospective
  framing, explicit instruction that the 2 questions per pillar must be
  "meaningfully different, not near-duplicates").
- **`app/schemas/ai_outcome.py::InnerReadingOutcomeGeneration`** — the six
  fields shared with check-in, plus `narrative`/`title`/`subtitle` (Inner
  Reading's own record content) and 4 `life_area_*` fields, all in one
  call. **`app/services/ai_outcome.py`** gained
  `generate_reading_outcome()`, same grounding pattern as
  `generate_checkin_outcome` (dims + focus_label as fixed facts, last-5
  `NarrativeEntry` summaries for continuity).
- **`app/services/questions.py`** — `next_inner_reading_increment()`
  (exact mirror of `next_check_in_increment`) and
  `get_or_generate_reading_question_set(db, on_date, increment)` rewritten
  to real AI + `(date, increment)` keying, replacing the old
  ordinal-only, never-resets scheme.
- **`app/services/scoring.py`** — removed `build_reading_narrative`,
  `build_reading_insight`, `build_reading_headline`, and (now fully
  unused) `build_balance`; `reading_content_for_plan` now reads
  `reading.narrative`/`.life_area_insights` directly off the row instead
  of a static library keyed by focus. **`app/services/content.py`** —
  removed `DEMO_READING_QUESTIONS`, `INSIGHT_LIBRARY`, `LIFE_AREA_INSIGHTS`,
  `HEADLINE_LIBRARY` (all now unused).
- **`app/api/v1/endpoints/readings.py`** — `get_questions` now `async`,
  calling the new increment helper + generator. `submit_inner_reading`
  rewritten to compute `dims`/`focus_key`/`focus_label`, call
  `generate_reading_outcome`, build the `InnerReading` row from the AI
  outcome's own content fields, pass the six shared fields into
  `apply_reflection_side_effects` as `narrative_content` (previously
  always `None` for Inner Reading — this is the one line that makes the
  shared cascade/snapshot/dashboard machinery light up for readings too),
  create a `NarrativeEntry`, set `.narrative_entry_id`, and persist
  `User.last_inner_reading_at`/`.inner_reading_count_today` at submit time
  only. No `cascade.py` change was needed — it already accepted
  `inner_reading_id`/`narrative_content` generically.
- **No endpoint or frontend changes** — `InnerReadingOut`'s shape was
  preserved exactly (content now real instead of static/canned), so
  `GET /inner-readings`, `GET /inner-readings/{id}`, and the already-wired
  `/inner-reading/history`/`/inner-reading/[id]/result` frontend pages
  needed zero changes; confirmed by checking
  `gio-member-app/lib/api/types.ts`'s `InnerReadingOut` already matches.

**Verified live**, full stack, real OpenAI calls, real Postgres:
- `GET /inner-readings/questions` → real 8-question generation, correctly
  retrospective framing, 2 meaningfully-different questions per pillar,
  `blueprint_version: "reading-v1-ai"`.
- `POST /inner-readings` on a fresh user → 201, real `narrative`/`title`/
  `subtitle`/`insight`/`reflection_question`/`life_area_insights` on the
  `InnerReading` row, a linked `NarrativeEntry`, and — new — a populated
  `InnerStateSnapshot` for `source_type="INNER_READING"` (previously
  always null for readings; now carries the same six real JSONB fields
  check-in's snapshots do).
- A second same-day Inner Reading (Premium test user) correctly triggers
  a separately-cached increment-2 question set and submits successfully
  with 0 quest XP (already completed today) but its own new badge/outcome
  logic still runs correctly.
- `GET /inner-readings` (list) and `GET /inner-readings/{id}` (detail)
  confirmed working unchanged, `is_premium_content`/`life_area_insights`
  gating confirmed correct for a Premium account.

## Added after this doc was first marked complete: listing category + emoji

The frontend's Inner Reading listing cards (hub's "Recent Readings" and
`/inner-reading/history`) needed a category chip and avatar emoji per
reading, matching a design the old mock's client-side `FOCUS_TAG` constant
used to produce from `resolveFocusKey(reading.dimensionScores)`. Ported
server-side rather than re-added client-side, since the real
`InnerReadingOut` has no `dimensionScores` field to compute from anyway:
new `content.py::READING_CATEGORY` (deterministic, keyed by
`resolve_focus_key()`, same principle as `FOCUS_COPY` — not AI, this is
listing/display metadata, not narrative) + `scoring.py::
reading_category_and_emoji()`, merged into `InnerReadingOut` via the
existing `reading_content_for_plan()` (always present, never
Premium-gated, unlike `narrative`/`life_area_insights`). No migration —
computed from the reading's already-stored pillar values, not a new
column. Verified live: `category`/`emoji` present and correct on
`GET /inner-readings`.

Frontend: `gio-member-app/docs/dev_log_0001.md` records the matching
change — `/inner-reading` (hub) migrated off the mock in the same pass
(closing that doc's last "known gap"), and both listing pages now render
`emoji`/`title`/`category`/`subtitle` straight from the API.
