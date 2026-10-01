from enum import Enum

from pydantic import BaseModel

from app.schemas.common import BilingualText
from app.services.content import AFFIRMATIONS, INSIGHTS, REFLECTION_QUESTIONS

# Dynamic enums built from the curated library (content.py) — see
# docs/behaviour_log_0011.md. The model's job for these three fields is
# now to *select* an id, not write free text; the schema itself
# constrains the output to a real id. Insight's prompt narrows this
# further to the 4 focus-matched candidates (content.py::INSIGHT_IDS_BY_FOCUS)
# via instruction, not the schema — Pydantic/JSON-schema enums can't be
# narrowed per-request, so that narrowing is prompt-level, same trust
# already placed in prompt-following elsewhere in this app.
AffirmationId = Enum("AffirmationId", {k: k for k in AFFIRMATIONS})
InsightId = Enum("InsightId", {k: k for k in INSIGHTS})
ReflectionQuestionId = Enum("ReflectionQuestionId", {k: k for k in REFLECTION_QUESTIONS})


class CheckInOutcomeGeneration(BaseModel):
    """text_format for the check-in outcome call — see
    docs/behaviour_log_0006.md Phase 4, docs/behaviour_log_0011.md, and
    gio-member-app/docs/behaviour_log_0002.md. `narrative_summary` is NOT
    user-facing (it becomes the new NarrativeEntry's summary, English-only
    since it's just system memory, never shown to the user) — every other
    freely-generated field is genuinely bilingual, written directly in
    both languages rather than translated after the fact. `title`/
    `subtitle` are new (docs/behaviour_log_0011.md), parity with Inner
    Reading's own."""

    insight_id: InsightId
    reflection_question_id: ReflectionQuestionId
    reminder: BilingualText
    current_focus: BilingualText
    friendly_advice: BilingualText
    affirmation_id: AffirmationId
    narrative_summary: str
    title: BilingualText
    subtitle: BilingualText


class InnerReadingOutcomeGeneration(BaseModel):
    """text_format for the Inner Reading outcome call — see
    docs/behaviour_log_0007.md Phase 4, docs/behaviour_log_0011.md, and
    gio-member-app/docs/behaviour_log_0002.md. Carries the same shared
    fields as CheckInOutcomeGeneration (these become InnerStateSnapshot's
    six JSONB fields via the shared cascade) — bilingual, since that
    target column is already JSONB regardless of trigger source — plus
    Inner Reading's own record-level content (narrative/title/subtitle)
    and the 4 life-area breakdown fields, which stay English-only for now:
    `InnerReading`'s own columns are plain String, not yet migrated to the
    bilingual JSONB shape (gio-member-app/docs/behaviour_log_0002.md Phase
    E, not done in this pass)."""

    # Shared with check-in — bilingual, feeds InnerStateSnapshot's JSONB columns.
    insight_id: InsightId
    reflection_question_id: ReflectionQuestionId
    reminder: BilingualText
    current_focus: BilingualText
    friendly_advice: BilingualText
    affirmation_id: AffirmationId
    narrative_summary: str

    # Inner Reading's own record content — still English-only, see docstring.
    narrative: str
    title: str
    subtitle: str

    # Replaces content.py::LIFE_AREA_INSIGHTS's static, focus-key-only copy.
    life_area_work: str
    life_area_relationships: str
    life_area_personal_growth: str
    life_area_conflict_management: str
