# behaviour_log_0001 — Core Personality vs. Inner State, and how AI fits

**Status:** Conceptual/behavioral spec — grounding an architectural
statement from the user against the actual current implementation, plus an
inferred AI-usage pattern from a newly-added reference file. Written for
review before any of the AI-generation half is built; nothing in this
document has been implemented yet beyond what's cited as "today."

## The two-track model

The system's purpose is to give a user insight into their **Core
Personality**, and to track an evolving **Inner State** that Emotional
Check-Ins and Inner Readings feed into. These are deliberately two
different kinds of data, updated on two different cadences, and the system
should keep treating them as architecturally separate rather than merging
them into one "profile" blob:

| | **Core Personality** | **Inner State** |
|---|---|---|
| What it represents | A stable identity | An evolving status |
| Derived from | Onboarding birthdate (+ an optional retaken baseline quiz) | Emotional Check-In and Inner Reading answers |
| Update cadence | Rare, deliberate | Frequent, passive (every submission) |
| User action to change it | Explicit — must retake a quiz | Implicit — happens as a side effect of checking in / reading |

## How this maps onto what's already built (`gio-backend`)

**Core Personality** → `app/models/personality.py::CorePersonality`, one
row per version, `is_current` flag marking the active one.
- Set once at onboarding, deterministically from `birthdate`
  (`app/services/scoring.py::score_from_birthdate`, and the richer
  standalone numbers in `app/services/numerology.py` —
  `life_path_number`/`birthday_number`/`talent_number`/
  `colour_affinity_scores`).
- Changing it requires an explicit "recalibration" — retaking the baseline
  A/B quiz (`app/api/v1/endpoints/personality.py::recalibrate`) — gated by
  a **24-hour cooldown** (`RECALIBRATION_COOLDOWN`) on top of the
  deliberate-action requirement. This is the concrete mechanism behind
  "rarely updated."

**Inner State** → `app/models/reflection.py::InnerStateSnapshot`, one row
per Check-In or Inner Reading submission (`source_type` +
exactly-one-of-two polymorphic FK back to whichever triggered it).
- Both `POST /check-ins` and `POST /inner-readings` compute dimension
  scores from the answers (`dimension_averages`, `resolve_focus_key`,
  `build_inner_state` in `app/services/scoring.py`) and, on every
  submission, run the same shared cascade
  (`app/services/cascade.py::apply_reflection_side_effects`) that writes a
  new snapshot, awards XP, updates streaks/garden, and generates a fresh
  `RecommendationProfile`. This is the concrete mechanism behind
  "evolving status."
- Check-In and Inner Reading differ in depth (4 questions vs. 8, see
  `app/services/questions.py`) but feed the **same** Inner State model —
  they're two input methods into one evolving signal, not two separate
  states.

## How AI is meant to be used — inferred from `sample-logic.py`

A reference file (`sample-logic.py`, an `AIBaziService` from a sibling
Chinese-numerology product) and a live `OPENAI_API_KEY`/`OPENAI_MODEL`
appeared in `gio-backend/.env` alongside this conversation. Read in full —
it encodes one specific, reusable principle, stated explicitly in its own
docstrings:

> "All calculations are done deterministically in Python, not by the
> model."

Concretely, the pattern is:

1. **Every number is computed in code first**, before the model is ever
   called — birthday number, life path number, talent number, a five-
   elements digit-frequency weighting, etc. Nothing numeric is delegated to
   the LLM.
2. **The prompt hands the model those numbers as fixed facts**, with an
   explicit instruction not to recompute or alter them (`"以下数值已由代码计算完成。
   不要重新计算或修改"` / "The following values have already been computed by
   code. Do NOT recalculate or modify them"). The model's only job is to
   write the *interpretive narrative* grounded on those facts.
3. **Structured outputs, not freeform text** — `client.responses.parse`
   against a `Pydantic` `text_format` schema (`ChineseElementalCalculation`
   / `EnglishElementalCalculation`), with `model_validator` enforcing exact
   array lengths per section (e.g. "Light" must be exactly 5 descriptions,
   "Potential Weaknesses" exactly 2). Malformed shape fails validation
   rather than silently shipping wrong content.
4. **A deterministic override step runs after generation as a safety net**
   — `generate_completion`'s `computed_weights` param re-writes whatever
   weight the model put in its output back to the code-computed value,
   in case the model didn't fully follow the "don't recalculate"
   instruction. Trust, but verify.
5. **Each language is generated independently**, not as one multilingual
   call and not as a translation-of-a-translation — `generate_chinese_content`
   and `generate_english_content` are separate prompts/calls with the same
   deterministic inputs, each free to phrase things naturally in that
   language rather than translating literally. A `translate_to_english`
   path exists as a fallback that *does* translate structurally, kept
   separate from the "generate natively" path.
6. **Results are persisted, not regenerated per view** — `ElementResult`
   rows keyed by `user_id`, queryable by latest or by year, mirroring the
   snapshot-on-event pattern `gio-backend` already uses for
   `RecommendationProfile`.

### What this implies for Gio's two tracks, if the same pattern is reused

- **Core Personality**: `numerology.py` already computes deterministic
  numbers from `birthdate` — currently flagged in its own docstring as a
  "best-effort" simplification that doesn't match the frontend's numbers.
  The `sample-logic.py` pattern suggests the eventual real-AI step is not
  "ask the model for the archetype," it's "compute the numbers precisely in
  code (closer to `sample-logic.py`'s richer Pythagorean + Five-Elements
  approach), then ask the model to *write the interpretation* of those
  fixed numbers." Low frequency (rarely updated) makes a real per-user API
  call affordable here.
- **Inner State**: `dimension_averages`/`resolve_focus_key`/
  `build_inner_state` already compute the deterministic dimension scores
  from check-in/reading answers. Today, `INSIGHT_LIBRARY`/
  `build_reading_narrative` (`app/services/content.py`,
  `app/services/scoring.py`) stand in for AI with a seeded/deterministic
  content-variant picker — explicitly documented elsewhere in this repo as
  a placeholder meant to be swapped for real generation later "with minimal
  structural change." The same grounded-narrative pattern applies: the
  scores stay code-computed, AI only writes the insight/narrative/
  reflection-question text around them. The open question this raises and
  doesn't yet answer: Inner State updates on **every** submission (not
  rarely, unlike Core Personality), so a live per-submission API call has a
  real cost/latency profile that the low-frequency Core Personality case
  doesn't — worth deciding deliberately rather than defaulting to "call the
  API every time," possibly reusing the existing
  `CheckInQuestionSet`/`InnerReadingQuestionSet` cache-by-key pattern for
  some part of this.

## Not yet decided (flagging rather than assuming)

- Whether Gio needs the bilingual (zh/en) generation split at all, or just
  English — `preferred_language` exists on `User` today but nothing in
  `gio-backend` currently branches content by it.
- Whether recalibration content (retaking the quiz) should also go through
  AI, or stay on the deterministic `score_baseline` path it uses today.
- The exact Pydantic schema(s) for Inner State's AI output, and whether
  validation should enforce fixed description counts the way
  `sample-logic.py`'s does.
- Caching/cost strategy for the high-frequency Inner State side.

This document exists to confirm the two-track mental model is understood
and to capture the one concrete pattern already available (`sample-logic.py`)
before any of it gets built — not to lock in the open questions above.
