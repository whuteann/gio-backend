# behaviour_log_0006 — Emotional Check-In: real generation & results parsing

**Status:** All 5 phases implemented/confirmed and verified. One open
question remains (Inner Reading's own future move to real AI).

## Phase 1 — implemented

Resolved during review: keep the existing `/check-ins/*` (plural) router
(open question 1) — `/check-in/*` singular endpoints described in Phase 5
below are not being built as a separate surface. The six narrative fields
on `InnerStateSnapshot` become one JSONB column each (open question 2),
holding `{"en": ..., "zh": ...}` — replacing the `_en`/`_zh` String pairs;
`summary_en`/`summary_zh` is a different field and was left untouched.

Implemented exactly as designed below: `app/models/reflection.py`
(`CheckInQuestionSet.increment` + composite `(date, increment)` unique
constraint, `CheckInSession.narrative_entry_id`, the six JSONB columns on
`InnerStateSnapshot`), `app/models/user.py`
(`last_check_in_at`/`check_in_count_today`). Migration:
`alembic/versions/e0d8e3049903_check_in_phase_1_models.py`. Verified live:
schema matches via `psql`, two `CheckInQuestionSet` rows for the same date
at different increments coexist, a duplicate `(date, increment)` is
correctly rejected by the constraint, and `POST /auth/register` /
`GET /me` still work with the new `User` columns in place.

## Phase 2 — implemented

Built as designed: `app/schemas/ai_questions.py::CheckInQuestionSetGeneration`
(4 named fields, one per pillar — the schema itself enforces exactly one
question per dimension, no list to validate), `app/services/ai_questions.py`
(the `responses.parse` call, prompt built from the spec's own wording — no
`temperature` param, the same model constraint `app/services/ai_personality.py`
already hit and documented in `behaviour_log_0004.md`, applied here too).
`app/services/questions.py::get_or_generate_checkin_question_set` is now
`async`, keyed by `(on_date, increment)`, calling into `ai_questions` on a
cache miss. New `next_check_in_increment(user) -> int` — pure calculation
(no DB writes; persisting the updated count is Phase 4's job, since it
should only happen on an actual submit, not on every questions fetch).

`app/api/v1/endpoints/checkins.py::get_questions` updated to call
`next_check_in_increment` and await the now-async generator — this was
necessary to keep the endpoint working (the function signature changed),
not a Phase 5 endpoint redesign. `submit_check_in` is untouched and still
broken per Phase 1's notes — that repair is Phase 4's.

Verified live: a fresh `GET /check-ins/questions` call triggers a real AI
generation (confirmed distinct, correctly-worded per-pillar questions, not
the old static text); a second user with no check-in history reuses the
exact same cached row (one row in the table, not two); calling the service
directly for increment 2 produces its own independently-generated,
separately-cached set; `next_check_in_increment` unit-tested across all
three cases (never checked in, checked in today, checked in yesterday).

Check-in questions are English-only for now — the spec doesn't ask for
bilingual questions here (unlike Core Personality), and the whole point of
the shared-cache design is one set reused across users regardless of
language.

## Current state (why this is needed)

`app/services/questions.py`'s caching mechanism already implements the
reuse pattern this feature wants — "first request for a key generates and
stores; everyone else that day reuses it" — but keyed **only by `date`**
(`CheckInQuestionSet.date`, `unique=True`). Every check-in on a given day,
regardless of whether it's a user's 1st or 5th that day, gets the **same**
question set. The new spec's per-user-per-day increment (1st check-in of
the day gets set #1, 2nd gets set #2, shared across users at that same
increment) needs a schema change, not just new generation logic.

`_generate_checkin_questions()` returns static text from
`content.py::DEMO_CHECKIN_QUESTIONS` — no AI involved yet, exactly as
`dev_log_0001.md` (gio-backend) originally scoped it as a placeholder.

**Also found while reading this code for this document**:
`POST /check-ins` (`checkins.py::submit_check_in`) currently calls
`personality.archetype` and `apply_reflection_side_effects` currently
builds `InnerStateSnapshot(**build_inner_state(dims))` — both reference
fields removed from their models in the `behaviour_log_0002`/`0003`
rebuild (`archetype`, `balance`, singular `summary`/`current_focus`).
**Check-in submission is currently broken** (would 500 on the
`personality.archetype` line, or the `InnerStateSnapshot` construction
right after). This isn't new breakage from this document — it's the same
deferred fallout flagged back in `behaviour_log_0002.md` — but it means
Phase 4 below has to actually repair this path, not just build on top of
working code.

## Phase 1 — Database models

**`CheckInQuestionSet`** (`app/models/reflection.py`): change the unique
key from `date` alone to a composite `(date, increment)`. Add an
`increment` column (`Integer`, "1st check-in of the day," "2nd," ...).
`UniqueConstraint(date, increment)` replaces the current `unique=True` on
`date`.

**`User`** (`app/models/user.py`): two new columns, per the explicit
design in the spec — `last_check_in_at` (`DateTime(timezone=True)`,
nullable) and `check_in_count_today` (`Integer`, default `0`). Reset logic
(`if last_check_in_at is not today: count = 0`) is a service-layer concern
(Phase 2/4), not the model's — the model just holds the two raw facts.

**`CheckInSession`**: gains a `narrative_entry_id` FK back to the
`NarrativeEntry` created for this check-in (nullable, `ondelete="SET NULL"`
so deleting a narrative entry doesn't cascade-delete the check-in it came
from) — needed for the "include a details page" requirement to link a
check-in to its own memory record if that's ever surfaced in a details
view. `summary` already exists (currently hardcoded to `"Daily emotional
check-in."` in `submit_check_in` — becomes real content in Phase 4).

**`NarrativeEntry`**: already exists exactly as needed
(`behaviour_log_0005.md`) — `source_type="CHECK_IN"` +
`check_in_session_id` + `summary`. No change required here.

**`InnerStateSnapshot`**: **resolved during review** — each of the six
fields (`insight`, `reflection_question`, `reminder`, `current_focus`,
`friendly_advice`, `affirmation`) becomes one JSONB column
(`{"en": ..., "zh": ...}`), replacing the `_en`/`_zh` String pair from
`behaviour_log_0002`/`0003`. Implemented — see the "Phase 1 — implemented"
note at the top of this document.

## Phase 2 — Question generation service

New/changed `app/services/questions.py`:

- `get_or_generate_checkin_question_set(db, on_date, increment)` — same
  get-or-create shape, now keyed by `(on_date, increment)`.
- Real AI generation replaces `_generate_checkin_questions()`, following
  the same grounded-prompt pattern as `app/services/ai_personality.py`
  (`behaviour_log_0004.md`): one `responses.parse` call against a new
  Pydantic schema (4 items, each `{dimension, text}`, dimension constrained
  to the 4 pillar keys in fixed order), system/user prompt built from the
  spec's own wording (4 questions, one per pillar in order, each expecting
  a 1-5 scale answer). No numbers or scoring asked of the model — only
  question text, consistent with "AI is responsible for question
  generation ONLY."
- **Increment resolution** (the part connecting to the new `User` columns):
  a small helper, e.g. `next_check_in_increment(user) -> int` — if
  `user.last_check_in_at` isn't today (UTC, matching the existing
  `gam.today_utc()` used elsewhere), the next increment is `1`; otherwise
  it's `user.check_in_count_today + 1`. This is what `GET /check-in/start`
  calls before asking `get_or_generate_checkin_question_set` for that
  increment's questions — exactly the Day-1/User-1/User-2 walkthrough in
  the spec.

## Phase 3 — Results parsing — confirmed, no code change needed

Open question 1 (below) is resolved: pillar values are computed within
the system, not by AI — matches this phase's assumption exactly.

The spec's requirement — "scored WITHIN the system... AI is responsible
for question generation ONLY" — is already how this works:
`app/services/scoring.py::dimension_averages()` groups normalized answers
by `dimension` and averages them; `resolve_focus_key()` derives the
"ongoing journey" focus from the result. As long as Phase 2's AI-generated
questions keep the existing `{dimension, text}` shape (one question per
pillar, in the fixed order given in the prompt), this layer needs no
change — it already only trusts `dimension` + the user's 1-5 answer,
never anything the model wrote beyond question text.

**Verified, not just assumed**: fetched a real Phase 2 AI-generated
question set and ran it through `normalize`/`dimension_averages`/
`resolve_focus_key` directly with several raw answer combinations — a
"balanced" set (5,5,1,5) correctly resolves to `"balanced"`; an isolated
low-energy set (1,4,2,4) correctly resolves to `"emotional_energy"`; a
missing-answer case correctly falls back to the documented default (50).

One real finding along the way, not a bug: a raw-value combination that
produces an *exact tie* in "need" between two dimensions (e.g.
`emotional_energy` and `inner_pressure` both scoring a need of 100)
resolves in favour of whichever dimension appears first in
`resolve_focus_key`'s own `needs` list — `emotional_energy` >
`mental_clarity` > `inner_pressure` > `grounding`, via Python's stable
sort. Undocumented before this pass; now confirmed and written down here
rather than left as an implicit accident of list order.

## Phase 4 — implemented

Built as designed, with the `CheckInSession.summary` open question
resolved first: **deterministic**, not AI — `f"Check-in — {focus_label}"`
built from `resolve_focus_key`/`focus_label_for` (new
`app/services/scoring.py::focus_label_for`), matching how the rest of the
app builds "systematic" content without a model call. `NarrativeEntry` is
the sole AI-facing memory record for the event; `CheckInSession.summary`
is just a short display label, so the two don't overlap in purpose.

- **`app/schemas/ai_outcome.py::CheckInOutcomeGeneration`** — 7 string
  fields: the six narrative fields plus `narrative_summary` (used for the
  `NarrativeEntry`, generated in the same call rather than a second round
  trip, as anticipated below).
- **`app/services/ai_outcome.py::generate_checkin_outcome`** — one
  `responses.parse` call grounded on the check-in's own `dims`/
  `focus_label` (fixed facts, not left to the model) plus the user's
  recent `NarrativeEntry` summaries as memory context. No `temperature`.
- **`app/services/narrative.py`** (new) — `get_or_create_narrative_profile`,
  `recent_narrative_summaries` (last 5, oldest-to-newest — the exact
  access pattern `behaviour_log_0005.md`'s model was built to serve),
  `create_narrative_entry`.
- **Inner State pillar update**: deterministic, via the now-repaired
  `app/services/cascade.py::apply_reflection_side_effects` (rewritten to
  match the current `InnerStateSnapshot` columns — no `balance`, JSONB
  field names/shapes — `build_inner_state` removed entirely, replaced by
  direct `InnerStateSnapshot(...)` construction from `dims` +
  `narrative_content`).
- **`app/api/v1/endpoints/checkins.py::submit_check_in`** — fully
  rewritten: computes `dims`/`focus_key`/`focus_label`, calls
  `generate_checkin_outcome`, threads the six fields into
  `apply_reflection_side_effects`, creates the `NarrativeEntry`, sets
  `CheckInSession.summary`/`.narrative_entry_id`, and persists
  `User.last_check_in_at`/`.check_in_count_today` (only here, at submit
  time — never at questions-fetch time, per Phase 2's design).

**Pre-existing breakage repaired** (flagged back in this doc's "Current
state" section, not new from this pass): both `checkins.py` and
`readings.py` queried `CorePersonality` with a since-removed
`is_current=True` filter and read a since-removed `.archetype` field.
Fixed in both call sites to use the `user.core_personality` relationship
and `.title_en`. Because `apply_reflection_side_effects` and
`build_recommendation` (`app/services/recommendation.py`) are shared by
both Check-In and Inner Reading submission, fixing this path for Check-In
required fixing Inner Reading's call site too (`readings.py`,
`scoring.py::build_reading_narrative`'s renamed `personality_title`
param) — Inner Reading's own move to real AI-generated outcomes is still
out of scope (open question 2 below).

**New bug found and fixed during live verification**:
`RecommendationProfile.core_personality_id` was `nullable=False`, but a
freshly-registered user who checks in before completing onboarding's Core
Personality step genuinely has none — `personality` is `None`,
`core_personality_id` is `None`, insert fails a NOT NULL constraint.
Made nullable in `app/models/recommendation.py`; migration
`alembic/versions/28313880ed51_recommendation_profiles_core_.py`.

**Verified live**, full stack, real OpenAI calls, real Postgres:
- `POST /check-ins` end-to-end on a fresh user (no Core Personality) →
  201, real six-field outcome + `narrative_summary` generated, a
  `NarrativeEntry` created and linked via
  `CheckInSession.narrative_entry_id`, `InnerStateSnapshot`'s pillar
  columns and six JSONB fields populated correctly, `colour_key` set from
  the recommendation, `User.last_check_in_at`/`.check_in_count_today`
  updated.
- A second same-day check-in for the same user correctly triggers
  increment-2 question generation (separately cached from increment-1,
  confirmed via `check_in_question_sets` rows), submits successfully, and
  correctly awards 0 quest XP (the `CHECK_IN` daily quest was already
  completed by the first check-in).
- `POST /inner-readings` (the shared cascade's other caller) still works
  end-to-end after the repair — 201, XP awarded, a badge evaluated.

## Phase 5 — Endpoints — implemented (already covered by the existing router)

Spec lists `GET /check-in/start`, `POST /check-in/submit`,
`GET /check-in/[id]/results` — **singular** `/check-in`, distinct from the
already-built, already-frontend-wired **plural** `/check-ins/*` router
(`GET /check-ins/questions`, `POST /check-ins`, `GET /check-ins`,
`GET /check-ins/{id}`, all live in `checkins.py` and called from
`gio-member-app/lib/api/reflections.ts`). **Resolved during review**:
kept the existing plural router — extended in place, no new endpoints, no
frontend route changes.

**Verified live, all four**, on a fresh user with two completed check-ins:
- `GET /check-ins/questions` → increment-resolution logic from Phase 2,
  live; response shape unchanged (`QuestionSetOut`).
- `POST /check-ins` → Phase 4 outcome generation, live; response shape
  unchanged (`CheckInSubmitResponse`) — the six narrative fields aren't
  echoed back in the submit response itself, only readable afterward via
  the linked `InnerStateSnapshot`/`GET /check-ins/{id}`.
- `GET /check-ins` (the "additional endpoint" the spec's list-view need
  maps to) → already existed (`list_check_ins`, entitlement-gated via
  `check_in_history_cutoff`, ordered `started_at.desc()`); confirmed 200
  with both sessions returned newest-first, each carrying its real
  deterministic `summary` and full `answers`. Already wired on the
  frontend too (`lib/api/reflections.ts::listCheckIns`) — nothing left to
  build here.
- `GET /check-ins/{session_id}` → already exists, now the "results" fetch,
  since `CheckInSession.summary`/`.narrative_entry_id` carry real content;
  confirmed 200 with correct detail shape.

**Added after this doc was first marked complete**: the frontend's new
`/check-in/[id]/result` results page needed a specific check-in's full AI
outcome (the six narrative fields + colour), not just its answers —
`GET /check-ins/{id}` alone doesn't carry that (it's on the linked
`InnerStateSnapshot`, keyed by `check_in_session_id`, not embedded in
`CheckInSessionOut`). Added **`GET /check-ins/{session_id}/results`**
(`CheckInResultsOut = {session, snapshot}`) rather than folding the
snapshot into the existing `CheckInSessionOut` response, to avoid an N+1
join on the plain list endpoint (`GET /check-ins`) — this maps directly
onto the spec's originally-listed `GET /check-in/[id]/results`.

**Bug found and fixed in the same pass**: `InnerStateSnapshotOut`
(`app/schemas/reflection.py`) still declared `balance: int`,
`current_focus: str`, `summary: str` — stale from before this document's
Phase 1 JSONB rework. `GET /state-snapshots/latest` (used by the frontend
dashboard) had been silently 500ing since that migration; nothing had
exercised it since. Fixed: flattened the six narrative fields to `_en`/
`_zh` pairs (matching `app/schemas/core_personality.py`'s existing
convention rather than a nested object), dropped `balance` (column no
longer exists) and the stale plain-string `summary` (the model's
`summary_en`/`summary_zh` is AI-grounding context, not user-facing, per
Phase 4's own docstring), added `colour_key`/`check_in_session_id`/
`inner_reading_id`. Since `from_attributes=True` can't flatten a JSONB
dict into `_en`/`_zh` fields automatically, added
`InnerStateSnapshotOut.from_model()` and updated
`snapshots.py::get_latest_snapshot` to use it. Verified live: 200 with
correct content instead of 500.

## Open questions

Resolved during review: endpoint naming (Phase 1), the
`InnerStateSnapshot` narrative fields becoming JSONB (Phase 1), pillar
values being computed in-system, not by AI (Phase 3), and
`CheckInSession.summary` being a deterministic label rather than AI
content (Phase 4). One remains, non-blocking:

1. **Reading's question-set cache** (`InnerReadingQuestionSet`, keyed by a
   single global `ordinal`) has the same "shared across users at the same
   ordinal" shape as this feature's target design, just without the daily
   reset. Should Inner Reading's generation also move to real AI as a
   follow-up now that this pattern is validated here (Phase 2/4), or is
   that explicitly out of scope for now? Not required for this feature —
   Inner Reading's submission path works correctly today, still on its
   existing demo question set and deterministic narrative.
