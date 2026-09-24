# behaviour_log_0005 — Narrative: system memory, not user-facing data

**Status:** Conceptual spec, recorded verbatim ahead of the database-model
plan (companion plan covers the "how to store it" side, for review before
implementation — same split as `behaviour_log_0002`/`0004`).

## What Narrative is

A third, distinct concept alongside Core Personality (stable identity) and
Inner State (evolving status, see `behaviour_log_0001.md`/`0002.md`):
**Narrative is the system's own ongoing memory of a user's activity** —
not something the user ever sees, and not something either Core Personality
or Inner State store themselves.

- It records an **AI analysis of the user's check-ins and Inner Readings**
  over time.
- Its purpose is **grounding context**: when generating an Inner State from
  a new Emotional Check-In or Inner Reading, Narrative is what supplies the
  continuity behind `InnerStateSnapshot`'s `insight`, `reflection_question`,
  `current_focus` ("ongoing journey"), `friendly_advice`, and `affirmation`
  fields (all already on the model per `behaviour_log_0002.md`, currently
  unpopulated by any real generation logic — see `behaviour_log_0004.md`'s
  "not yet decided" list, which already flagged Inner State's generation
  strategy as an open question this now starts to answer).
- **Never user-facing.** Purely internal memory/personalization state — no
  endpoint should ever return raw Narrative content to a client the way
  `CorePersonality`'s fields are meant to be displayed.

## Stated structure

- Each **user** is linked to a **narrative profile**.
- Each **narrative profile** is linked to a **narrative entry**, which
  carries a short (~20 word) AI-generated summary.

## How this is expected to fit the existing system

The natural integration point is `app/services/cascade.py::apply_reflection_side_effects`
— the one function both `POST /check-ins` and `POST /inner-readings`
already call on every submission, which is where `InnerStateSnapshot` rows
get created today. Narrative would plug in around that same moment:
existing memory read *in* as grounding context before generating this
event's Inner State content, and a new Narrative record written *out*
afterward capturing what this event added to the ongoing picture — the
same "read prior context, act, write new context" shape a stateful
conversational memory needs, applied to check-ins/readings instead of
chat turns.

This wiring is **not** part of this pass — `apply_reflection_side_effects`
isn't touched here. This document and its companion plan are the data
model only; generation logic is separate future work, consistent with how
Core Personality's generation was built only after its model shape was
settled.

## Open question the implementation plan needs to resolve

"Each narrative profile is linked to a narrative entry" reads singular,
but "ongoing memory... records an AI analysis of check-ins and Inner
Readings" (plural, accumulating over time) points at a **history** —
one entry per check-in/reading event, the same one-row-per-event pattern
already used for `InnerStateSnapshot`. The implementation plan resolves
this explicitly rather than guessing silently either way.
