"""The "narrative prompt" — a single templated block of already-computed
facts, assembled here in code rather than left for the AI to gather or
invent. See docs/behaviour_log_0012.md. This is the same "numbers first,
AI narrates/selects around them" principle as `app/services/ai_outcome.py`,
applied to a new consumer: the product-recommendation AI step
(`app/services/ai_recommendation.py`).

Ingredients, all read from data that already exists by the time a
check-in/Inner Reading finishes: the unified recommended colour (the same
one `build_recommendation` just resolved for this submission — passed in,
not recomputed), the triggering snapshot's four dims, the last 5
`NarrativeEntry` summaries (now spanning check-ins, readings, *and*
journals per this same behaviour log), and a rollup of recent journaling
from the existing `journal.py::build_journal_insights`.
"""

from sqlalchemy.orm import Session

from app.models.journal import JournalEntry
from app.models.reflection import InnerStateSnapshot
from app.models.user import User
from app.services.gamification import today_utc
from app.services.journal import build_journal_insights
from app.services.narrative import get_or_create_narrative_profile, recent_narrative_summaries


def build_narrative_prompt(
    db: Session,
    user: User,
    *,
    snapshot: InnerStateSnapshot,
    focus_label: str,
    colour: dict,
) -> str:
    profile = get_or_create_narrative_profile(db, user)
    summaries = recent_narrative_summaries(db, profile)
    if summaries:
        memory_block = "\n".join(f"- {s}" for s in summaries)
    else:
        memory_block = "(none yet — this is this user's first recorded reflection)"

    journal_entries = db.query(JournalEntry).filter_by(user_id=user.id).all()
    insights = build_journal_insights(journal_entries, today_utc())
    if insights["entries_this_week"] > 0:
        journal_block = (
            f'{insights["entries_this_week"]} journal entries this week '
            f'({insights["entries_delta"]:+d} vs. last week), most common mood '
            f'"{insights["top_mood"]}", most common theme "{insights["top_theme"]}".'
        )
    else:
        journal_block = "No journal entries this week."

    return f"""\
This user's current focus is "{focus_label}". Their supportive colour \
right now is {colour["name"]} ({", ".join(colour["traits"])}).

Inner state: Emotional Energy {snapshot.emotional_energy}/100, Mental \
Clarity {snapshot.mental_clarity}/100, Inner Pressure {snapshot.inner_pressure}/100, \
Grounding {snapshot.grounding}/100.

Recent reflections, oldest to newest:
{memory_block}

Recent journaling: {journal_block}
"""
