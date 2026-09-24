# behaviour_log_0002 — Inner State & Core Personality: stored shape

**Status:** Conceptual/data-shape spec from the user, recorded verbatim
against current implementation. Supersedes/extends `behaviour_log_0001`'s
two-track model with the exact field lists each track is meant to carry.
Companion implementation plan (DB models, for review) covers the "how to
build it" side of this — this document is the "what it is" side.

## Inner State

The evolving current status of a user, updated by both Emotional Check-In
and Inner Reading. Carries:

- The 4 pillars: **Emotional Energy, Mental Clarity, Inner Pressure,
  Grounding**
- The **current Colour Recommendation**
- A **latest insight**
- A **reflection question**
- A **"Reminder for you"**
- An **ongoing journey** (e.g. "Finding Clarity")
- A **"friendly advice"**
- An **"affirmation"**
- A **summary** — distinct from the other narrative fields above: this one
  is not user-facing copy, it's AI-facing context. It exists so the AI step
  has a condensed grounding text to consume when generating:
  - Colour recommendation (after a check-in or reading)
  - Product recommendation

## Core Personality

The rarely-changing identity at the core of the user's profile in this
system. Carries:

- **title** (e.g. "The Open Horizon")
- **subtitle**
- **overview**
- **Birthday Number** + **Birthday Number content**
- **Life Path Number** + **Life Path Number content**
- **Talent Number** + **Talent Number content**
- **Colour values** — one score per colour (e.g. Scarlet 90, Ocean 75); each
  colour has a field and a value
- A **summary** — same purpose as Inner State's: AI-facing grounding text
  for the same two downstream processes (colour recommendation, product
  recommendation), not user-facing copy.

## Gap against what's currently implemented (`gio-backend`)

**Inner State** — `app/models/reflection.py::InnerStateSnapshot` already
has: `emotional_energy`, `mental_clarity`, `inner_pressure`, `grounding`
(the 4 pillars ✓), `current_focus` (the "ongoing journey" ✓), `balance`
(no equivalent in the new spec), `summary` (already exists, but today it's
short user-facing copy from `FOCUS_COPY` — e.g. "You're in a steady place
across the board..." — not AI-facing grounding context; the new spec's
`summary` is a different thing wearing the same field name and needs to be
reconciled, not assumed identical).

Not currently on `InnerStateSnapshot` at all: colour recommendation
(currently lives on a separate, separately-triggered `RecommendationProfile`
row), insight, reflection question, "Reminder for you", "friendly advice",
affirmation. Of these, `insight`/`reflection_question` exist today — but
only on `InnerReading`, not on `InnerStateSnapshot`, and **not at all** for
check-ins (`CheckInSession` has no equivalent fields). Since Inner State is
explicitly meant to be updated by *both* check-ins and readings with the
*same* shape, these need to live on the shared model, not the
reading-only one.

**Core Personality** — `app/models/personality.py::CorePersonality`
currently stores an archetype-quiz shape entirely: `archetype`, `icon`,
`thinking`/`emotional_sensitivity`/`adaptability`/`willpower` (4 pillars,
different pillars than Inner State's), `overall_explanation`,
`pillar_explanations`, `assessment_version`. None of the new spec's fields
exist today: no `title`/`subtitle` split, no `overview`, no
`birthday_number`/`life_path_number`/`talent_number` (these are computed
live and thrown away in `app/services/numerology.py`, never persisted), no
per-colour score storage (`colour_affinity_scores` in the same file is also
computed live and discarded), no `summary`.

`title: "The Open Horizon"` reuses an exact existing archetype name
(`app/services/content.py::ARCHETYPES["open_horizon"]["name"]`) — the
*concept* of an archetype-like label survives, just restructured. Whether
the underlying 4-pillar quiz/recalibration mechanism
(`BASELINE_ASSESSMENT`, `score_baseline`, the 24h-cooldown recalibration
endpoint) survives alongside this, or is being superseded by a purely
birthdate/numerology-derived model, is the open structural question the
implementation plan needs to resolve before modeling `CorePersonality`.

## Note on naming collision

`InnerReading` already has its own `title`/`subtitle` columns today
(reading-level headline flavor text, e.g. "Need for Recovery" /
"You appeared to need more personal space...") — unrelated to Core
Personality's new `title`/`subtitle` (archetype-level identity label, e.g.
"The Open Horizon"). Same field names, two different concepts on two
different models. Flagging so the implementation plan doesn't conflate
them.
