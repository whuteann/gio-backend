# behaviour_log_0013 — Emotional Check-In: question & result generation, current configuration and improvement levers

**Status:** Report only, per instruction — an audit of exactly how
check-in questions and results are generated today, to base quality
decisions on. Nothing changed in this pass. Inner Reading shares the same
two service files (`ai_questions.py`, `ai_outcome.py`), so it's referenced
throughout for contrast, but the focus and all "should we change this"
framing below is Emotional Check-In, as asked.

## Part 1 — The full flow, step by step

**Questions (once per day per `(date, increment)`, not per user):**
1. Frontend calls `GET /check-ins/questions`.
2. `next_check_in_increment(user)` — pure calculation, no DB write —
   works out which check-in-of-the-day this is (1st, 2nd, ...) from
   `user.last_check_in_at`/`check_in_count_today`.
3. `get_or_generate_checkin_question_set(db, today, increment)` — a
   cache lookup on `(date, increment)`. **First** request for that key,
   from **any** user, calls the model; every other request that day
   reuses the stored row. This is the load-bearing cost control: one
   generation serves everyone who checks in that day (or that "2nd
   check-in of the day", etc.), not one generation per user per check-in.
4. On a cache miss: `ai_questions.generate_checkin_questions()` — one
   `responses.parse` call, `reasoning={"effort": "medium"}`, structured
   output (`CheckInQuestionSetGeneration`, one field per pillar,
   `{en, zh}` each). No dims, no user data, no memory — the prompt is
   completely generic (full text in Part 2).
5. Stored as `[{dimension, text, text_zh}]` in `CheckInQuestionSet.questions` (JSONB).

**Answers → deterministic scoring (zero AI):**
6. User answers all 4 (1 per pillar) on a 1-5 scale, submits.
7. `normalize()`: linear 1-5 → 0-100 (`round(((raw-1)/4)*100)`).
8. `dimension_averages()`: averages normalized values per pillar — for
   check-in specifically this is a no-op average over exactly 1 answer
   per pillar (Inner Reading has 2 answers/pillar, where this actually
   averages).
9. `resolve_focus_key(dims)` — see Part 4, this is the one piece of
   "which need matters most" logic in the entire pipeline, and it's a
   simple deterministic rule, not AI.

**Result generation (one live call per submission, this IS personalized):**
10. `user.core_personality` is fetched and `personality_title` extracted
    — **used later only for a deterministic recommendation sentence, never
    passed into the AI prompt** (Part 6 — this is the headline finding).
11. `recent_narrative_summaries(db, profile)` — last 5 `NarrativeEntry.summary`
    strings, oldest→newest, spanning check-ins **and** Inner Readings
    **and** journal entries (cross-source memory).
12. `ai_outcome.generate_checkin_outcome(dims, focus_label, focus_key, recent_narrative_summaries)`
    — one `responses.parse` call, **no `reasoning` param set** (Part 3),
    structured output (`CheckInOutcomeGeneration`). Selects 3 ids from
    curated libraries, freely writes 6 more fields. Full prompt in Part 2.
13. `apply_reflection_side_effects()` (`cascade.py`) — no AI itself —
    builds `InnerStateSnapshot` from the dims + the 6 narrative fields,
    records the 3 unlocks, runs XP/streak/garden/badges/rewards, and
    calls `build_recommendation()` (the colour/routine/product engine,
    `behaviour_log_0012.md`).
14. `CheckInSession.title`/`.title_zh`/`.subtitle`/`.subtitle_zh` set from
    the outcome; a new `NarrativeEntry` is written from `narrative_summary`
    (this submission's own memory trace, feeding step 11 for the *next*
    submission — check-in, reading, or journal alike).
15. Response returns `session_id` + XP/streak/badge outcome only — the
    frontend fetches the actual content separately via
    `GET /check-ins/{id}/results` (session + `InnerStateSnapshot`).

## Part 2 — The exact current prompts

**Question generation** (`ai_questions.py`), system message:
> "You are a thoughtful wellness check-in designer writing for an app
> called Gio. You must strictly follow the required JSON structure."

Full user prompt (verbatim, check-in variant):
```
Generate a set of 4 questions for the purpose of evaluating the current
inner state of the user, based on these 4 pillars, in order. Each question
should expect a scale from 1 to 5 as its answer:

- emotional_energy: Emotional Energy (Drained -> Energised)
- mental_clarity: Mental Clarity (Foggy -> Clear)
- inner_pressure: Inner Pressure (Light -> Heavy)
- grounding: Grounding (Unsteady -> Rooted)

Output rules:
- One question per pillar, written as a single natural sentence ending in a question mark.
- The question should clearly invite a 1-5 self-rating along that pillar's named spectrum (e.g. the emotional_energy question should read naturally whether the honest answer is "drained" or "energised") — do not mention the number scale explicitly in the question text itself, the UI shows the 1-5 scale separately.
- Do not ask about any pillar other than the one named for that field.
- Plain text only, no markdown, no numbering, no emoji.
- Write each question in both English (`en`) and Chinese (`zh`) — genuine, natural phrasing in each language, not a literal translation of one into the other.
```
That's the **entire** input. No user history, no dims, no personality,
no prior questions to avoid repeating — every element of variety comes
from the model's own sampling, not from anything the code feeds it.

**Result generation** (`ai_outcome.py`), same system message pattern
("warm, perceptive wellness companion"). Full user prompt (verbatim,
check-in variant — `{...}` are the actual runtime values):
```
A user just completed an emotional check-in.

IMPORTANT: the following values have already been computed by code. Do NOT
recalculate or alter them — use them exactly as given as the grounding for
your writing:
- Emotional Energy: {dims["emotional_energy"]}/100
- Mental Clarity: {dims["mental_clarity"]}/100
- Inner Pressure: {dims["inner_pressure"]}/100
- Grounding: {dims["grounding"]}/100
- Current focus (already determined): {focus_label}

Recent memory of this user's last check-ins/readings, oldest to newest
(use this for continuity — do not contradict it, and reference a pattern
across entries if one is genuinely present, but don't force a connection
that isn't there):
{memory_block}

Choose an affirmation_id from this list (pick whichever best fits this
specific moment — do not invent a new one):
{all 20 affirmations, "AFF01": "text", ...}

Choose a reflection_question_id from this list, ideally one that connects
to the insight you're pointing at:
{all 20 reflection questions, "REF01": "text", ...}

Choose an insight_id from this list only (these are the ones that match
today's resolved focus — do not pick from outside this list):
{only the 4 insights matching today's focus_key, "INS0x": "text", ...}

Write the following:
- affirmation_id, reflection_question_id, insight_id: as instructed above.
- reminder: one short, warm reminder for the user to carry with them today.
- current_focus: a short (2-5 word) phrase naming the user's ongoing
  journey right now, in the spirit of "{focus_label}" but written as
  natural, personal phrasing rather than repeating that label verbatim.
- friendly_advice: one concrete, small, doable suggestion for today.
- narrative_summary: NOT user-facing, English only regardless of the
  fields above. A factual, third-person summary of this check-in in 20
  words or fewer, written to be read back as memory context for a
  *future* generation like this one — plain and dense, no flourishes, no
  direct address to the user.
- title: a short (2-5 word) headline for this check-in, suitable for a
  history list (e.g. "Steady Ground", "Gentle Reset").
- subtitle: one short sentence expanding on the title.

Output rules:
- reminder, current_focus, friendly_advice, title, and subtitle are each
  written in both English (`en`) and Chinese (`zh`) — genuine, natural
  phrasing in each language, not a literal translation of one into the
  other. narrative_summary is a single plain string, English only.
- Every free-text field is plain text (no markdown, no bullet points).
- Keep each field genuinely short — this is a daily check-in, not an essay.
```
That's the entire input for the "personalized" half of the pipeline: 4
numbers, 1 derived label, up to 5 lines of prior memory, and 44 fixed
library entries to choose 3 ids from. Nothing about *who this person is*
(Part 6).

## Part 3 — Configuration as actually running

- **Model**: `settings.openai_model`, code default `"gpt-4.1"`, but the
  live `.env` overrides it to `OPENAI_MODEL=gpt-5.6-luna` — confirmed by
  reading the running container's actual config, not just the code
  default. Both question and outcome generation use this same model.
- **Reasoning effort**: question generation explicitly passes
  `reasoning={"effort": "medium"}`. Outcome generation passes **no
  `reasoning` param at all** — an asymmetry with no comment explaining
  it, on the call that does objectively more (bilingual free writing +
  3-way constrained selection vs. just writing 4 questions).
- **Temperature**: deliberately omitted everywhere in this app — an
  existing code comment (`ai_personality.py`) says the configured model
  rejects that parameter.
- **Caching**: questions are cached per `(date, increment)`, shared
  across every user — see Part 1. Outcomes are never cached; every
  submission is a fresh call.
- **Retries / timeouts**: no `max_retries` or `timeout` override on any
  of the four `AsyncOpenAI()` clients in this codebase
  (`ai_outcome.py`, `ai_questions.py`, `ai_recommendation.py`,
  `ai_personality.py`) — all rely on the SDK's own defaults.
- **Error handling on the check-in path**: `submit_check_in()` has no
  `try/except` around `generate_checkin_outcome()`. If that call fails
  or times out, the whole request fails — no snapshot, no XP, no streak,
  nothing persisted for that submission. This is the same failure shape
  the product-recommendation pipeline had before `behaviour_log_0012.md`
  hardened it to degrade gracefully; check-in/Inner Reading's own AI call
  has not had that treatment.

## Part 4 — What's deterministic vs. AI, precisely

Only one piece of "which need matters" logic exists in the whole
pipeline, and it's pure code, not AI (`scoring.py::resolve_focus_key`):
```python
needs = [
    ("emotional_energy", 100 - dims["emotional_energy"]),
    ("mental_clarity", 100 - dims["mental_clarity"]),
    ("inner_pressure", dims["inner_pressure"]),
    ("grounding", 100 - dims["grounding"]),
]
needs.sort(key=lambda n: n[1], reverse=True)
top_key, top_need = needs[0]
return top_key if top_need >= 55 else "balanced"
```
Winner-takes-all against a fixed 55-point threshold, 5 possible outcomes
(4 pillars + "balanced"). No code comment documents why 55 specifically,
and the second-highest need is discarded entirely once a winner is
picked — a user who's both quite drained (need 60) *and* under real
pressure (need 58) is labelled "emotional_energy" only; "inner_pressure"
being nearly as strong never reaches the AI prompt in any form.

The curated libraries the AI selects from (`content.py`):

| Library | Size | Candidates shown per call |
| --- | --- | --- |
| Affirmations | 20 | all 20, every time |
| Reflection questions | 20 | all 20, every time |
| Insights | 20 | only the 4 matching today's `focus_key` |

Insight is the tightest pool by far — a user who lands in the same focus
bucket on consecutive check-ins (common; "balanced" and whichever pillar
someone chronically struggles with both recur a lot) is choosing from
the *same 4 insights* every time, and the prompt gives the model nothing
— not even the ids it picked last time — to deliberately vary the pick.
Memory is prose summaries only; there's no structured "here's what
you've already shown this user" signal for any of the 3 selected fields.

## Part 5 — Personalization: where it exists, where it doesn't

- **Questions**: zero personalization. The exact same 4 questions (both
  languages) go to every user who checks in that day (or that Nth
  check-in of the day) — this is the direct cost of the shared-cache
  design, not an oversight; it's what makes question generation cheap
  regardless of daily active users.
- **Results**: personalized per submission, but only on three axes —
  *today's own numbers*, *the single resolved focus label*, and *up to 5
  lines of past summaries*. Nothing about the user's stable identity
  (Core Personality) reaches this prompt at all.

## Part 6 — Confirmed, still-open gap: Core Personality isn't read

`submit_check_in()` fetches `user.core_personality` and extracts
`personality_title` — then passes it only to `apply_reflection_side_effects()`,
which in turn hands it only to `build_recommendation()`, where its
*sole* use is one deterministic sentence template
(`f"A small, doable step suited to {title_for_reason.lower()}."`). It
never reaches `generate_checkin_outcome()`'s prompt. The "warm,
perceptive wellness companion" writing someone's reminder, advice,
title, and subtitle has no access to that person's Core Personality
title, subtitle, overview, or number narratives when writing them — only
today's 4 numbers and a short memory trail.

This is the exact gap `behaviour_log_0010.md` flagged when comparing
against the Auren UX deck ("AI reflection prompt doesn't read Core
Personality profile as input despite deck/onboarding implying it
should"). It has not been addressed since — confirmed directly by
reading today's `generate_checkin_outcome()` signature, which still has
no personality parameter at all.

## Part 7 — Summary of concrete levers, most to least direct

1. **Feed Core Personality into the outcome prompt.** Almost certainly
   the single highest-leverage change for "quality" as commonly meant —
   it's the gap between generic wellness copy and something that
   actually sounds like it knows the person. `personality_title` is
   already being fetched at the call site; it just needs to reach the
   prompt (and the model likely wants more than the title — overview,
   maybe a top-2 colour affinity — to write with rather than just naming
   an archetype label).
2. **Insight repetition risk.** Only 4 candidates per focus bucket, no
   anti-repetition signal. Either widen the per-bucket pool, or pass the
   selected ids from the last N submissions (not just prose summaries)
   so the model can deliberately avoid repeats.
3. **Reasoning-effort asymmetry.** Question generation gets
   `effort: "medium"`; outcome generation gets the model's default. Worth
   a deliberate decision either way, not an accidental gap.
4. **No fallback on outcome-generation failure.** A transient model
   failure currently loses the entire check-in (no snapshot, no XP, no
   streak progress) — the same failure mode the recommendation pipeline
   had before it was hardened in `behaviour_log_0012.md`. Worth deciding
   whether check-in deserves the same treatment (e.g., a deterministic
   fallback outcome so the submission still completes).
5. **`resolve_focus_key`'s single-winner logic.** Undocumented threshold
   (55), and the second-highest need is dropped entirely even when it's
   nearly as strong as the winner. Worth revisiting if results are
   feeling too blunt for genuinely mixed states.
6. **Question personalization is structurally impossible today** without
   changing the cache key away from pure `(date, increment)` — worth
   naming explicitly, since "improve question quality" could easily mean
   "make them feel personal," and that specific improvement has a direct
   cost tradeoff (one generation per user/day instead of one per day
   total) that should be a deliberate choice, not a side effect.

Nothing above has been changed. This is the base to decide from —
happy to turn any subset of Part 7 into an implementation plan once you've
said which levers matter most.
