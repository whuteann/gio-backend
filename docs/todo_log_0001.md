# todo_log_0001 — Emotional Check-In: question quality fine-tuning

**Status:** Deferred backlog. `behaviour_log_0006.md`'s question generation
(`app/services/ai_questions.py::generate_checkin_questions`) is live and
functionally correct — real AI generation, correctly cached per
`(date, increment)`, correctly consumed by the deterministic scoring layer
— but the questions themselves are "passable," not tuned. Logged here
rather than folded into `behaviour_log_0006.md` since that document tracks
a shipped feature's phases, not open-ended prompt quality work.

## What's observed, not just assumed

Wording is **not stable across generations** — the same pillar comes out
phrased differently set to set, since nothing anchors the register beyond
the one-paragraph prompt in `ai_questions.py`. Two real examples pulled
from this session's own verification runs, both for `inner_pressure`:

- "How would you rate your inner pressure right now, from light to heavy?"
- "How light or heavy does your inner pressure feel right now?"

Neither is wrong on its own, but a user checking in on consecutive days
currently has no guarantee of a consistent voice — closer to "a different
person wrote today's question" than "the same app asking again."

## Candidate directions (not decided, not started)

1. **Few-shot the prompt** — 2-3 exemplar question sets embedded in
   `_PROMPT`, to anchor register/sentence shape instead of relying on the
   one-paragraph description alone.
2. **Tighten the output contract** — the current rules ban explicit scale
   mentions and cross-pillar bleed, but don't constrain sentence length,
   punctuation style, or forbid compound/double-barrelled phrasing
   explicitly.
3. **A lightweight QA pass before caching** — since a bad set is shared by
   every user at that `(date, increment)` for the rest of the day (by
   design — `behaviour_log_0006.md`'s caching model), a single bad
   generation currently has no safety net. Worth deciding whether that
   needs a validation step (rule-based or a second model call) before
   `get_or_generate_checkin_question_set` commits it, or whether it stays
   accepted risk given the cost/latency tradeoff.
4. **Revisit once real usage exists** — this is fine-tuning against taste
   right now (no user feedback signal yet). Worth checking whether the
   product actually wants to collect a "did this question feel off" signal
   before investing further here.

## Explicitly out of scope for this backlog item

- Bilingual (`zh`) question generation — deliberate, documented decision
  in `behaviour_log_0006.md`, not a quality gap.
- The outcome-generation side (`app/services/ai_outcome.py`, the six
  narrative fields) — not raised as a concern; this item is questions only.
