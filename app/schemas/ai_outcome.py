from pydantic import BaseModel


class CheckInOutcomeGeneration(BaseModel):
    """text_format for the check-in outcome call — see
    docs/behaviour_log_0006.md Phase 4. Six user-facing narrative fields
    plus a 7th, narrative_summary, which is NOT user-facing — it becomes
    the new NarrativeEntry's summary (the system's own memory of this
    event), generated in the same call rather than a second round trip."""

    insight: str
    reflection_question: str
    reminder: str
    current_focus: str
    friendly_advice: str
    affirmation: str
    narrative_summary: str


class InnerReadingOutcomeGeneration(BaseModel):
    """text_format for the Inner Reading outcome call — see
    docs/behaviour_log_0007.md Phase 4. Carries the same six shared fields
    as CheckInOutcomeGeneration (these become InnerStateSnapshot's six
    JSONB fields via the shared cascade, unchanged) plus Inner Reading's
    own record-level content (narrative/title/subtitle, InnerReading's own
    columns, kept for frontend compatibility — see the open questions in
    docs/behaviour_log_0007.md) and the 4 life-area breakdown fields
    (replacing the old static content.py::LIFE_AREA_INSIGHTS lookup)."""

    # Shared with check-in's six fields.
    insight: str
    reflection_question: str
    reminder: str
    current_focus: str
    friendly_advice: str
    affirmation: str
    narrative_summary: str

    # Inner Reading's own record content (InnerReading.narrative/title/subtitle).
    narrative: str
    title: str
    subtitle: str

    # Replaces content.py::LIFE_AREA_INSIGHTS's static, focus-key-only copy.
    life_area_work: str
    life_area_relationships: str
    life_area_personal_growth: str
    life_area_conflict_management: str
