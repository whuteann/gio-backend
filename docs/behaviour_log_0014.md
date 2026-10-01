# behaviour_log_0014 — Results calculation, persistence, and evaluation prompts: full audit (Check-In + Inner Reading)

**Status:** Report only — an audit, not a change. Continues
`behaviour_log_0013.md` (which scoped mostly to Check-In, with Inner
Reading for contrast) with full, equal coverage of both, plus the piece
0013 didn't do: a complete table-by-table map of what actually gets
persisted per submission. All code re-read fresh for this pass, not
recalled from 0013 — one finding below (`summary_en`/`summary_zh`, Part
3) is new and wasn't in 0013.

## Part 1 — The deterministic calculation (identical logic, both features)

Zero AI involvement in the numbers themselves — `scoring.py`, same
functions for both:

```python
def normalize(raw_value: int) -> int:          # 1-5 -> 0-100
    return round(((raw_value - 1) / 4) * 100)

def dimension_averages(answers: list[dict]) -> dict[str, int]:
    # averages normalized_value per dimension key; missing dims default to 50
```

- **Check-in**: 1 answer per pillar, so `dimension_averages` is a no-op
  average over a single value.
- **Inner Reading**: 2 answers per pillar (from the reflection+planning
  pair, `behaviour_log_0013`/this session's prompt work), genuinely
  averaged.

Then the one piece of "which need matters" logic, also shared, also pure
code:
```python
def resolve_focus_key(dims: dict[str, int]) -> str:
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
Winner-takes-all against an undocumented 55-point threshold; the
second-highest need is discarded entirely once a winner is picked. Same
finding as `behaviour_log_0013.md` Part 4 — repeated here because it
feeds identically into both features' AI prompts as `focus_label`.

## Part 2 — What is saved, table by table

**Raw answers** — `check_in_answers` / `inner_reading_answers`: one row
per question answered — `dimension`, `question_text` (the exact question
text the user actually saw, in whichever language they were in —
verified this session), `answer_value` (1-5), `normalized_value` (0-100),
`order_index`. Kept forever, never gated by plan.

**The session/reading record itself:**

| Column | `check_in_sessions` | `inner_readings` |
| --- | --- | --- |
| Dims (4 pillars) | *not stored here* — only on the snapshot | stored directly, `SmallInteger` each |
| `title`/`title_zh` | AI-written, bilingual (this session's Phase D work) | AI-written, **English only** |
| `subtitle`/`subtitle_zh` | AI-written, bilingual | AI-written, **English only** |
| `narrative` | — (check-in has no long-form narrative) | AI-written, **English only**, 3-5 sentences |
| `insight` | — (lives on the snapshot instead, bilingual) | AI-selected from library, **English half only** — `INSIGHTS[id]["en"]`, the Chinese half of the same library entry is discarded at write time |
| `reflection_question` | — (lives on the snapshot instead) | same as above — English half only |
| `life_area_insights` | — | JSONB, 4 AI-written paragraphs (work/relationships/personal_growth/conflict_management), **English only**, always generated and saved for every reading regardless of plan |
| `summary`/`result_summary` | deterministic label, `f"Check-in — {focus_label}"` | deterministic label, `f"Inner Reading — {focus_label}"` |
| `narrative_entry_id` | FK to the `NarrativeEntry` this submission produced | same |

Inner Reading's own record fields being English-only is the confirmed,
still-open gap from `gio-member-app/docs/behaviour_log_0002.md` Phase E —
restated here because it's directly relevant to "what is saved."

**Depth-gating happens at read time, not write time** — worth being
precise about, since it affects what "saved" means: `scoring.py::reading_content_for_plan()`
always has the full AI-generated `narrative`/`life_area_insights`
available on the row; a free-plan read truncates `narrative` to 100 words
and nulls out `life_area_insights` **in the API response only** — the
underlying row is never touched. Upgrading to Premium retroactively
reveals full depth on readings taken while free. `category`/`emoji` are
never gated (computed deterministically, always shown).

**The shared "Inner State" record** — `inner_state_snapshots`, produced
by *either* a check-in or a reading (exactly one FK set, enforced by a
check constraint): the 4 dims again (denormalized here too, so this
table alone answers "what was my state on date X" regardless of source),
`colour_key`, and six bilingual JSONB fields —
`insight`/`reflection_question`/`reminder`/`current_focus`/`friendly_advice`/`affirmation`,
each `{"en": ..., "zh": ...}`. `insight`/`reflection_question`/`affirmation`
are genuinely bilingual (curated library, full entry preserved here —
unlike `InnerReading.insight` above, which throws away the `zh` half).
`reminder`/`current_focus`/`friendly_advice` are freely written and
bilingual since this session's Phase D work.

**New finding — two unused columns**: `InnerStateSnapshot.summary_en`/
`.summary_zh` exist, are commented "AI-facing grounding context for
colour + product recommendation," and are **never written anywhere in
the codebase** — confirmed by searching the full app tree. The actual
recommendation-prompt grounding (`narrative_prompt.py`,
`behaviour_log_0012.md`) builds its context directly from the snapshot's
dims + `focus_label` at call time, not from these columns. They appear
to predate that design and were never cleaned up — always `NULL` today,
harmless but dead weight on every snapshot row.

**System memory** — `narrative_entries`: one row per check-in, reading,
*or* journal entry (cross-source, `behaviour_log_0002.md`/0012), a single
`summary` string (~20 words, English only, by design — never shown to a
user), plus exactly one FK back to whichever source produced it. This is
the entire memory mechanism: `recent_narrative_summaries()` reads the
last 5, oldest→newest, and that's the only history either outcome-prompt
ever sees.

**Gamification unlock ledger** — `user_unlocked_content`: one row per
`(user, category, item_id)` the first time that curated-library id is
ever assigned to that user — append-only, never revoked, drives the
"Growth Tree"/collection UI (`behaviour_log_0011.md`). Independent of
`user_badges` (threshold-based, e.g. streak/XP milestones) — two
separate, non-overlapping systems both triggered from the same
submission.

**Downstream, briefly** (full detail in `behaviour_log_0012.md`): XP,
streak, garden stage, badge evaluation, and a same-day
`RecommendationProfile`/`RecommendationItem` bundle all fan out from the
same submission via `cascade.py::apply_reflection_side_effects` — not
re-audited here since that's a separate, already-documented pipeline.

## Part 3 — The exact prompts that guide evaluation (verbatim, current)

Both features call `ai_outcome.py`, same system message:
> "You are a warm, perceptive wellness companion writing for an app
> called Gio. You must strictly follow the required JSON structure."

*(Note: this is a different, older system message than the one just
redesigned for question generation this session — `ai_outcome.py` was
not touched during that work. If you want the "warm companion" persona
here to match the newer "Auren" framing/register now used for questions,
that's a follow-up, not yet done.)*

**Shared library-selection block**, injected into both prompts (all 20
affirmations, all 20 reflection questions, only the 4 insights matching
today's `focus_key`):
```
Choose an affirmation_id from this list (pick whichever best fits this
specific moment — do not invent a new one):
{20 affirmations}

Choose a reflection_question_id from this list, ideally one that connects
to the insight you're pointing at:
{20 reflection questions}

Choose an insight_id from this list only (these are the ones that match
today's resolved focus — do not pick from outside this list):
{only the 4 insights for today's focus_key}
```

**Check-in's outcome prompt**, full text:
```
A user just completed an emotional check-in.

IMPORTANT: the following values have already been computed by code. Do NOT
recalculate or alter them — use them exactly as given as the grounding for
your writing:
- Emotional Energy: {dims}/100  [x4 pillars]
- Current focus (already determined): {focus_label}

Recent memory of this user's last check-ins/readings, oldest to newest
(use this for continuity — do not contradict it, and reference a pattern
across entries if one is genuinely present, but don't force a connection
that isn't there):
{memory_block — up to 5 lines}

{library-selection block above}

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
  *future* generation like this one.
- title: a short (2-5 word) headline for this check-in.
- subtitle: one short sentence expanding on the title.

Output rules:
- reminder, current_focus, friendly_advice, title, and subtitle are each
  written in both English and Chinese — genuine, natural phrasing in
  each, not a literal translation. narrative_summary is English only.
- Keep each field genuinely short — this is a daily check-in, not an essay.
```
No `reasoning` param set on this call (contrast: question generation
explicitly sets `effort: "medium"`).

**Inner Reading's outcome prompt** — same shared-field instructions as
above, plus:
```
- narrative: a fuller, 3-5 sentence reflective read of this moment — this
  is the main body of the reading, more depth than the single-insight
  fields above, in a warm second-person voice.
- life_area_work, life_area_relationships, life_area_personal_growth,
  life_area_conflict_management: one short, concrete paragraph each,
  translating this reading into a specific implication for that life
  area — practical, not generic filler.

Output rules:
- reminder, current_focus, and friendly_advice are bilingual.
  narrative_summary, narrative, title, subtitle, and the 4 life_area_*
  fields are English only, for now.
```
Notably: this prompt still frames itself as grounded only in *today's
numbers* + *focus label* + *5 lines of memory* — none of the new
reflection/planning voice, archetype ("thinking, creative person"), or
"closeness to source" framing just built into Inner Reading's
*questions* has been carried over to how its *results* are written. The
questions now ask about a stalled project or a role quietly changing;
the result-writing prompt has no idea that happened — it only ever sees
the 4 final numbers, not what was actually asked or how the user
answered in context.

## Part 4 — Findings, ranked

1. **Core Personality still isn't read by either outcome prompt.**
   Restated from `behaviour_log_0013.md` — still true, confirmed again
   this pass. `personality_title` is fetched in both endpoints and
   reaches only `build_recommendation()`'s deterministic sentence
   template, never the AI prompt.
2. **Insight-selection repetition risk is no longer theoretical.** 0013
   flagged this as a risk (only 4 candidates per focus bucket, no
   anti-repetition signal). This session then *empirically proved* the
   exact same model (`gpt-5.6-terra`) reliably collapses onto a small
   fixed set when given few examples with no explicit variety pressure —
   twice: the "kettle" image for check-in's `emotional_energy` question
   (3/3 runs), and Inner Reading mapping its 4 seed examples 1:1 onto
   its 4 pillars (3/3 runs) until the seed pool was deliberately widened
   and an explicit anti-mapping instruction added. Insight selection has
   the identical shape of risk (a small fixed candidate set, no
   memory-of-recent-picks signal) and has not had the same fix applied.
   This is now a demonstrated failure mode of this specific model under
   these conditions, not a hypothetical one.
3. **The new question-generation voice and the still-old result-writing
   voice have diverged.** Check-in's questions now live in vivid, tight,
   moment-grounded prose; Inner Reading's now live in reflective,
   archetypal, "closeness to source" language. Neither feature's
   *outcome* prompt (`ai_outcome.py`) was touched — it still uses the
   original "warm, perceptive wellness companion" system message and
   generic "write a reminder/advice/title" instructions for both
   features identically, with no awareness of the richer question that
   was actually asked. A user could be asked a beautifully specific
   question about a stalled project, and get back a title/subtitle
   written with zero knowledge that framing existed.
4. **Two dead columns**: `InnerStateSnapshot.summary_en`/`.summary_zh`,
   documented as recommendation-prompt grounding, never written. Either
   wire them up or remove them — currently pure unused schema.
5. **`InnerReading.insight`/`.reflection_question` discard the Chinese
   half of an already-bilingual library entry** at write time
   (`INSIGHTS[id]["en"]` only) — the same content is fully bilingual one
   table over, on `InnerStateSnapshot`. A cheap partial fix ahead of the
   full Phase E migration, if wanted: store both halves now even before
   the rest of Inner Reading's own fields get migrated.
6. **`reasoning` effort asymmetry** (question generation: `medium`;
   outcome generation: unset) and **no error handling** around either
   outcome call (a transient failure loses the whole submission) —
   both restated from `behaviour_log_0013.md`, still unaddressed.

Nothing above has been changed. This is the current state to decide
from — happy to turn any subset of Part 4 into an implementation plan.
