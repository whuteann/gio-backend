"""AI-generated Emotional Check-In questions.

Same principle as app/services/ai_personality.py: the model's job is the
question text only. It never sees or produces any numbers — no scoring,
no scale values beyond being told the answer format is 1-5. Results
parsing (app/services/scoring.py) stays entirely deterministic, trusting
only the fixed `dimension` key each question is generated under, exactly
per docs/behaviour_log_0006.md's "AI is responsible for question
generation ONLY."

Bilingual since gio-member-app/docs/behaviour_log_0002.md: each question
comes back written in both English and Chinese in the same call (not a
translation of one into the other), so the one shared/cached set still
serves every user regardless of their language — no extra generation
cost, just a slightly larger response.
"""

from openai import AsyncOpenAI

from app.config import settings
from app.schemas.ai_questions import CheckInQuestionSetGeneration, InnerReadingQuestionSetGeneration

_client = AsyncOpenAI(api_key=settings.openai_api_key)

_SYSTEM_MESSAGE = (
    "You are a creative, caring, and thoughtful wellness check-in designer writing for an app called Auren. You are sensitive to the react to certain life check-in questions to determine current mood and personality"
    "You must strictly follow the required JSON structure."
)

_PROMPT = """\
Generate a set of 4 questions to evaluate a user's current inner state, \
one per pillar below, in order. Each expects a 1-5 self-rating as its \
answer.

The 4 Pillars:
- emotional_energy: Emotional Energy (Drained -> Energised)
- mental_clarity: Mental Clarity (Foggy -> Clear)
- inner_pressure: Inner Pressure (Light -> Heavy)
- grounding: Grounding (Unsteady -> Rooted)

HOW TO WRITE EACH QUESTION — moment first, then the ask:
For each pillar, picture one small, specific, everyday moment — not a \
topic, a *moment*: something a person could be standing inside of right \
now. Let that moment carry the pillar's emotional texture, then let the \
question grow out of it in the same breath, rather than stating a moment \
and then separately bolting on a generic question about it.

Draw from life's ordinary textures — work, people, plans, mood, energy, \
motivation — but always a moment, never a category label. For \
inspiration only (invent your own in this spirit; never reuse these \
verbatim):
- the stretch of quiet right after a meeting ends
- typing a reply, deleting it, and starting over
- the third cup of coffee that doesn't land like the first one did
- opening a notebook to a blank page
- waking up before the alarm, for no clear reason
- the pull between starting now and starting "in five minutes"

The 4 moments in one set must be genuinely different from each other —
different scenes, different textures, no two pillars sharing a topic.

VOICE & CRAFT:
- Economy: every word earns its place. No throat-clearing ("Think about \
a time when...", "Consider how...") — land inside the moment immediately. \
One clean sentence, roughly 15-22 words.
- Prosody: read it aloud in your head before settling on it. It should \
carry a natural breath and a soft landing on the question mark, not a \
pile-up of clauses. Vary the rhythm across the 4 questions — they \
shouldn't all scan the same way or open with the same shape.
- Prose: concrete and sensory over abstract or clinical. Prefer one \
small, specific image (a cup of coffee going cold, a phone screen \
lighting up in a quiet room) to a general statement about feelings. \
Avoid therapy-speak and cliché ("How are you really feeling?", "Take a \
moment to check in with yourself") — write like someone who notices \
things, not a questionnaire. A touch of quiet wonder is welcome; this \
should feel like an invitation to notice, not an interrogation.
- Sentence building: let the moment do the work of the setup, then pivot \
straight into the pillar's question within that same sentence — two \
separate sentences (moment, then question) only if the rhythm genuinely \
calls for it.

Output rules:
- One question per pillar, a single natural sentence ending in a \
question mark.
- The question should clearly invite a 1-5 self-rating along that \
pillar's named spectrum (e.g. the emotional_energy question should read \
naturally whether the honest answer is "drained" or "energised") — do \
not mention the number scale explicitly, the UI shows the 1-5 scale \
separately.
- Do not ask about any pillar other than the one named for that field.
- Plain text only, no markdown, no numbering, no emoji.
- Write each question in both English (`en`) and Chinese (`zh`) — \
genuine, natural phrasing in each language, matching the same moment and \
the same craft standard above, not a literal translation of one into \
the other.
"""


async def generate_checkin_questions() -> CheckInQuestionSetGeneration:
    response = await _client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _SYSTEM_MESSAGE},
            {"role": "user", "content": _PROMPT},
        ],
        text_format=CheckInQuestionSetGeneration,
        reasoning={"effort": "medium"},
        # No `temperature` — see app/services/ai_personality.py's note on
        # the configured model rejecting that parameter.
    )
    return response.output_parsed


# Inner Reading — see docs/behaviour_log_0007.md Phase 2 and
# gio-backend/docs/behaviour_log_0013.md. Same contract as check-in's
# questions above (question text only, no numbers), doubled to 2
# questions per pillar — but a deliberately different *voice* from
# check-in's, per direct product direction: check-in lives in small,
# ordinary moments; Inner Reading lives in reflection and planning, for
# someone thinking and creating their way through a real challenge. Its
# own system message (below) reinforces that register on top of the
# prompt itself.
_READING_SYSTEM_MESSAGE = (
    "You are a contemplative, perceptive guide designing a deeper reflective practice — an \"Inner Reading\" — for an app called Auren. "
    "You write for thinking, creative people navigating real challenges and working to overcome them, helping them measure how close they feel to their own inner source through reflection and quiet planning. "
    "You must strictly follow the required JSON structure."
)

_READING_PROMPT = """\
Generate a set of 8 questions (2 per pillar) for a deeper reflective \
practice called an "Inner Reading" — slower and more considered than a \
quick daily check-in, and built for a different purpose: measuring how \
close this person feels right now to their own source — the wellspring \
of energy, clarity, resolve, and grounded selfhood a thinking, creative \
person draws on while facing a real challenge and working to overcome \
it. Evaluate the user's current state across these 4 pillars, in order. \
Each question expects a 1-5 self-rating as its answer.

The 4 Pillars:
- emotional_energy: Emotional Energy (Drained -> Energised)
- mental_clarity: Mental Clarity (Foggy -> Clear)
- inner_pressure: Inner Pressure (Light -> Heavy)
- grounding: Grounding (Unsteady -> Rooted)

HOW TO WRITE EACH PAIR — reflection, then planning, not a snapshot:
For each pillar, invent one real challenge, threshold, or creative \
tension this specific person may be navigating right now — something \
that would only occur to you after actually thinking about it, not the \
first idea that comes to mind. Let the FIRST question look back over the \
last few days at how they've moved through it; let the SECOND look \
ahead — at what they're building toward, or what this state means for \
their next step. Together the pair should read as one person's thought \
deepening, not two versions of the same ask.

For inspiration only — a wide sample of the *register* to write in, not \
a menu to assign one-per-pillar. There are far more of these than you \
need; invent something none of them cover, and never reuse any of them \
verbatim:
- a project that stalled and had to be picked back up
- the point in a hard week you almost let go, and didn't
- a decision you keep circling without landing on
- an old pattern trying to repeat itself, caught this time
- a conversation you've been avoiding because it matters too much
- realizing partway through something that you'd need to start over
- the quiet resolve it takes to try again after being wrong
- weighing whether to push forward alone or ask for help
- an idea that resisted every attempt to shape it into something real
- the gap between the plan you made and what actually happened
- returning to something you'd set aside, unsure if it still mattered
- sitting with an unfinished thought that refuses to resolve

The 4 challenges across the 4 pillars must be genuinely different from \
one another — different tensions, no two pillars drawing on the same \
one, and none of them a straight one-to-one pull from the list above.

VOICE & CRAFT:
- Economy: unhurried but not loose — roughly 18-28 words per question, \
every word earned. No throat-clearing ("Think about a time when...").
- Prosody: this is the slower practice, so let the rhythm breathe — one \
considered pause before the question lands is welcome — but keep each \
sentence whole, not fragmented. Vary the shape across the 8 questions.
- Prose: draw on the imagery of someone who thinks and creates for a \
living — a compass, a current, a threshold, a root system, a horizon, an \
unfinished draft — rather than the small domestic scenes of a daily \
check-in. Let closeness to one's own source live in the metaphor, never \
name it clinically ("evaluate your connection to your source" is wrong; \
an image that carries that feeling is right). Avoid new-age cliché \
("align your energy", "manifest") as firmly as you'd avoid therapy-speak.
- Sentence building: let the challenge do the work of the setup in each \
question, then pivot into that pillar's ask within the same breath.

Output rules:
- Two questions per pillar, each a single natural sentence ending in a \
question mark, and the two must be meaningfully different from each \
other (reflection vs. planning, per above) — not near-duplicates.
- The question should clearly invite a 1-5 self-rating along that \
pillar's named spectrum — do not mention the number scale explicitly, \
the UI shows the 1-5 scale separately.
- Do not ask about any pillar other than the one named for that field.
- Plain text only, no markdown, no numbering, no emoji.
- Write each question in both English (`en`) and Chinese (`zh`) — \
genuine, natural phrasing in each language, matching the same challenge \
and the same craft standard above, not a literal translation of one into \
the other.
"""


async def generate_reading_questions() -> InnerReadingQuestionSetGeneration:
    response = await _client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _READING_SYSTEM_MESSAGE},
            {"role": "user", "content": _READING_PROMPT},
        ],
        text_format=InnerReadingQuestionSetGeneration,
        reasoning={"effort": "medium"},
        # No `temperature` — see app/services/ai_personality.py's note on
        # the configured model rejecting that parameter.
    )
    return response.output_parsed
