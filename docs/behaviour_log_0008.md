# behaviour_log_0008 — Module backbone: the whole shape, confirmed

**Status:** Architectural overview / confirmation record, not a feature
plan. Written to capture the intended end-to-end shape of Core
Personality → Emotional Check-In / Inner Reading → Narrative →
Recommendation as a single picture, cross-checked against what
`behaviour_log_0001`–`0007` actually built, and against
`database_audit_2026-09-23.md`'s live findings. One piece of the intended
shape — Narrative/AI feeding recommendations — is not yet real; recorded
here as the one open gap this document exists to make explicit.

## The intended shape, as described and confirmed

1. **Onboarding** — a user supplies their birthdate once. `CorePersonality`
   is generated from it: numerology breakdown (birthday/life-path/talent
   numbers) and a 5-colour breakdown (scarlet/russet/gold/forest/ocean
   scores), plus bilingual title/subtitle/overview text. Stable identity,
   not re-scored per reflection — `behaviour_log_0002.md`.
2. **Two reflection types, same 4 pillars, different depth**:
   - **Emotional Check-In** — a quick, present-moment pulse: 4 questions
     (1 per pillar: emotional_energy, mental_clarity, inner_pressure,
     grounding), meant to be done often. `behaviour_log_0006.md`.
   - **Inner Reading** — a slower, more considered state reading: 8
     questions (2 per pillar, retrospective "last few days" framing) over
     the same 4 pillars, plus a fuller narrative and a 4-life-area
     breakdown (work/relationships/personal_growth/conflict_management).
     Deeper on the *same* pillars, not a personality re-assessment —
     Core Personality stays the one stable-identity layer; Inner Reading
     is a deeper snapshot of current state, same category as check-in.
     `behaviour_log_0007.md`.
   - Both: pillar scores are always computed deterministically in code
     (`scoring.py::dimension_averages`/`resolve_focus_key`) from the raw
     1-5 answers — the AI's job is question text and outcome narrative
     only, never the numbers. Six AI-written narrative fields (insight,
     reflection_question, reminder, current_focus, friendly_advice,
     affirmation) land on `InnerStateSnapshot` and are what the dashboard
     cycles through.
3. **Narrative — the system's own memory, not user-facing** —
   `NarrativeEntry` records one short AI-written summary per check-in/
   reading (`behaviour_log_0005.md`). Confirmed use today: the last 5
   entries (`narrative.py::recent_narrative_summaries`) are handed to
   `ai_outcome.py`'s prompt as continuity context, so a new check-in or
   reading's insight/reflection/reminder text can reference a real
   pattern across visits instead of writing cold every time.
4. **Recommendations, grounded on current state** — the target shape:
   using the user's Narrative history and current `InnerStateSnapshot`,
   an AI step plus a real product-catalog API generates a ranked,
   explained product/routine/colour recommendation.

## Where the current implementation stops short of that shape

Step 4 is **not yet built as described** — this is the one real gap
between the intended backbone and what's running today:

- `recommendation.py::build_recommendation` makes **no AI call**. It's
  deterministic: `resolve_focus_key(dims)` → static
  `content.py::FOCUS_COPY`/`FOCUS_TO_COLOUR` → colour/routine copy, then
  product selection is a plain tag intersection.
- It **never reads `NarrativeEntry`** — grepped `recommendation.py` and
  `cascade.py` to confirm. (`cascade.py`'s `narrative_content` parameter
  is a different, confusingly similarly-named thing — the six AI outcome
  fields being written onto the snapshot, not a read of the Narrative
  memory table.) Recent-history personalization is claimed in Premium
  product reason text ("Chosen from your recent history...") but nothing
  actually queries history to back that claim — `database_audit_2026-09-23.md`
  finding F8.
- Products come from `recommendation.py::_fetch_products_stub()` — a
  hardcoded list of 7 items, not a third-party ecommerce API. This is
  already flagged as a TODO in that file's own docstring: *"in the real
  system they'd come from a third-party ecommerce API call, then an AI
  step would pick from them using the user's inner state + Core
  Personality. Neither the API call nor the AI step exist yet."*
- Core Personality *is* used, but only for wording (the personality title
  in a routine's reason text), not as a scoring input to product
  selection.

Everything upstream of this (onboarding → Core Personality, both
reflection types' question/outcome generation, Narrative recording) is
real and live, verified end-to-end in `behaviour_log_0006.md`/`0007.md`.
The recommendation step is the one link in the chain still standing in
for future work, consistent with how it was originally scoped — not a
regression, just not started yet.

## Not itself a plan

This document doesn't propose phases for closing the recommendation gap —
that's future work, likely its own `behaviour_log_000X` once scoped
(real product API integration, an AI selection step grounded on Narrative
+ snapshot, deciding how Core Personality's fuller scores factor in
beyond wording). Recorded here only to make the current boundary explicit
so the next pass starts from an accurate picture, not an assumed one.
