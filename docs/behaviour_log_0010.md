# behaviour_log_0010 — Auren UX deck vs. current implementation

**Status:** Comparison record, not a plan. Source:
`GioMembershipPlatform/Auren_User_Experience.pdf` (7 pages: What It Is,
User Experience overview, Onboarding, Emotional Check-In, Inner Reading,
Product Recommendation, Dashboard AI Affirmations). One naming note before
the comparison: the deck calls the product **"Auren"**/**"Auren+"**
throughout, not "Gio"/"Premium" — read as the same product under a
different working name in this design artifact, not a different product;
not acted on here, flagged only so it isn't mistaken for a mismatch in
the findings below.

## Confirmed matches — deck describes what's actually built

**Onboarding (deck p.3)**: birthdate → fixed numerology calculations
(Birthday/Life Path/Talent Number, 5 colour-affinity scores) with AI
writing only the interpretation, output in English + Chinese, "a stable
profile, carried into future AI reflections." Matches
`behaviour_log_0002.md`–`0004.md` exactly — numerology is deterministic,
Core Personality's text generation is genuinely bilingual (unlike
check-in/Inner Reading, confirmed below).

**Emotional Check-In (deck p.4)** — 4 AI-generated questions, one per
pillar → 1-5 answers become 0-100 values → an AI reflection → saved to
two places (Inner State: 4 scores + guidance; User Narrative Memory: a
short AI summary). Matches `behaviour_log_0006.md` precisely, field for
field, **with one real gap** — see below.

**Inner Reading (deck p.5)** — 8 AI-generated questions, two per pillar,
retrospective framing → each pair averaged on the same 0-100 scale → a
current-state report (narrative, insight, a reflection question; Auren+
unlocks full depth) → saved to the same two places. Matches
`behaviour_log_0007.md` precisely. The deck's own footer note —
**"TODAY: Same scoring; no extra weighting"** — is a direct, independent
confirmation of `behaviour_log_0007.md`'s Phase 3 finding
(`dimension_averages()` treats both reflection types identically, no
special weighting for Inner Reading's 8 answers vs. check-in's 4). Not a
new finding, a validation of an existing one.

**Product Recommendation (deck p.6)** — Inner State (4 pillars) →
Recommendation Engine, labeled **"Rule-based today"** → colour + product
recommendations, explicitly **"BUILT: Focus rules + 7-item demo
catalogue"** vs. **"PLANNED: Memory-aware AI + live catalogue."** This is
an exact, independent match to `behaviour_log_0008.md`'s own finding
(deterministic tag-matching, `_fetch_products_stub()`, no AI call, no
Narrative read) — the deck itself documents the identical BUILT/PLANNED
boundary this document already confirmed by reading the code. Strong
cross-check that `behaviour_log_0008.md`'s analysis was correct, not
overcautious.

**Dashboard AI affirmations (deck p.7)** — inputs are "4 pillar values
from the latest reflection" + "User Narrative Memory: last 5 reflection
summaries," output is AI guidance "written when you reflect" and "saved
in Inner State." The deck names exactly six fields: **Affirmation /
Insight / Reflection / Focus / Advice / Reminder** — a one-to-one match
to `InnerStateSnapshot`'s six JSONB columns
(`affirmation`/`insight`/`reflection_question`/`current_focus`/
`friendly_advice`/`reminder`). Confirms the field set is right; the
*display* of that field set is the gap below.

## Gaps found — deck describes something not yet built

1. **The AI reflection doesn't actually read the Core Personality
   profile.** Deck p.4, step 3 ("UNDERSTAND"): "Uses your scores, profile
   and recent memory." Checked directly: `ai_outcome.py::generate_checkin_outcome`
   and `generate_reading_outcome` both take only `dims`, `focus_label`,
   `recent_narrative_summaries` — no personality input at all.
   `checkins.py`/`readings.py` both compute `personality_title` and pass
   it to `apply_reflection_side_effects` (for the recommendation's
   routine-wording only), **never to the outcome-generation prompt
   itself**. Onboarding's own page (p.3) states the profile is meant to
   be "carried into future AI reflections" — that carry-through doesn't
   happen today for either reflection type's outcome text. This is the
   one concrete design-vs-implementation gap in the check-in/reading
   generation logic itself.
2. **The dashboard shows 2 of the 6 fields, not a cycling view of all
   six.** Confirmed directly in `dashboard.tsx`: only `current_focus`
   (as a Chip) and `insight` (as a paragraph) are ever read via
   `localizedSnapshot()`. `reflection_question`, `reminder`,
   `friendly_advice`, and `affirmation` are generated and stored on every
   submission but **never displayed anywhere in the app** today. The
   deck's p.7 mockup (`‹ AFFIRMATION: "One small step is enough for this
   moment." ›`, dot pagination, labeled "Proposed cycling view") is
   explicitly marked proposed, not claimed as built — so this isn't a
   contradiction, but it does mean 4 of the 6 AI-written fields are
   currently generated for no visible purpose.
3. **"Give Inner Reading more influence" is an explicit, named future
   direction, not yet built.** Deck p.5's footer pairs "TODAY: same
   scoring, no extra weighting" (confirmed above) against "PROPOSED: Give
   Inner Reading more influence" — i.e. weighting a fresh Inner Reading's
   pillar values more heavily than a check-in's when both feed the same
   `InnerStateSnapshot`/dashboard state. Nothing in the current
   `scoring.py`/`cascade.py` does this; each submission's `InnerStateSnapshot`
   is independent, dashboard just reads the latest one regardless of
   which type produced it. Noted as a real, named proposal — not
   currently scoped into any phase of `behaviour_log_0006.md`/`0007.md`.

## Open question — content format needs your confirmation, not my assumption

Your own gloss on the deck described check-in as recording "a short
summary title and summary of check-in (AI)." Two different things could
be meant, and the current schema only has one of them:

- `NarrativeEntry.summary` — already exists, already AI-written (≤20
  words, factual, third-person, memory-only, never shown to the user).
  If "summary" in your description refers to this, nothing is missing.
- A **`title`** field on `CheckInSession` itself, AI-generated, the way
  `InnerReading.title`/`.subtitle` already work — this does **not**
  exist. `CheckInSession.summary` is deterministic
  (`f"Check-in — {focus_label}"`, resolved explicitly in
  `behaviour_log_0006.md` Phase 4 as "a short label, never AI" — the
  opposite of what "summary title... (AI)" would imply).

Before this becomes a design decision I act on: **is a new AI-generated
title being requested for `CheckInSession` (mirroring Inner Reading's
title/subtitle), or does the existing `NarrativeEntry.summary` already
satisfy what the deck is describing?** Not assumed either way here.

## Not acted on in this document

No code changed. This is the requested compare-and-report step only —
the three gaps above and the one open question are inputs to whatever
comes next (e.g. an extension of the language-connection work already in
progress, or its own phase plan), not started here.
