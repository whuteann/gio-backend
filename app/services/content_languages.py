from app.services.languages import SUPPORTED

READING_FIELDS = ("title", "subtitle", "narrative", "life_area_insights")
PERSONALITY_FIELDS = (
    "title", "subtitle", "overview", "summary", "birthday_number_points",
    "life_path_number_points", "talent_number_points",
)


def column(kind: str, field: str, language: str) -> str:
    return field if kind == "readings" and language == "en" else f"{field}_{language}"


def missing(row, kind: str, language: str) -> list[str]:
    fields = READING_FIELDS if kind == "readings" else PERSONALITY_FIELDS
    return [column(kind, name, language) for name in fields
            if not getattr(row, column(kind, name, language), None)]


def apply_missing(row, proposed: dict) -> None:
    # Re-check after generation: a live background task may have completed
    # while the model was running. Its content must win over this repair.
    for name, value in proposed.items():
        if value and not getattr(row, name, None):
            setattr(row, name, value)


def mark_actual_languages(row, kind: str) -> None:
    row.languages_ready = [lang for lang in SUPPORTED if not missing(row, kind, lang)]
    row.generation_status = "READY" if len(row.languages_ready) == len(SUPPORTED) else "PARTIAL"


def catalog_copy(row, kind: str, language: str) -> dict:
    if kind != "readings":
        return {}
    from app.services.content import INSIGHTS, REFLECTION_QUESTIONS
    proposed = {}
    # These fields came from fixed catalogs. Match their existing text,
    # rather than inventing a new insight or question for a historical row.
    for field, catalog in (("insight", INSIGHTS), ("reflection_question", REFLECTION_QUESTIONS)):
        for entry in catalog.values():
            if any(getattr(row, column(kind, field, source), None) == entry.get(source)
                   for source in SUPPORTED if entry.get(source)):
                proposed[column(kind, field, language)] = entry.get(language)
                break
    return proposed


async def proposed_body(db, row, kind: str, language: str) -> dict:
    if not missing(row, kind, language):
        return {}
    if kind == "readings":
        from app.services.reading_language import field, fill_secondary_language
        if not field(row, "narrative", row.primary_language or "en"):
            raise RuntimeError("Reading has no primary narrative; manual review required")
        if not await fill_secondary_language(db, row, language):
            raise RuntimeError("Reading language generation failed; row left unchanged")
        return {column(kind, field, language): getattr(row, column(kind, field, language))
                for field in READING_FIELDS}

    from app.services.ai_personality import generate_core_personality_content
    if row.user is None or row.user.birthdate is None:
        raise RuntimeError("Personality has no saved birthdate; manual review required")
    content = await generate_core_personality_content(
        birthdate=row.user.birthdate.isoformat(), birthday_number=row.birthday_number,
        life_path_number=row.life_path_number, talent_number=row.talent_number,
        colour_weights={key: getattr(row, f"{key}_score")
                        for key in ("scarlet", "russet", "gold", "forest", "ocean")},
        language=language,
    )
    return {column(kind, field, language): value for field, value in content.model_dump().items()}


async def repair_one(db, kind, entity_id, language):
    from app.models.personality import CorePersonality
    from app.models.reflection import InnerReading
    model = {"readings": InnerReading, "personalities": CorePersonality}[kind]
    row = db.get(model, entity_id)
    if row is None:
        return
    proposed = catalog_copy(row, kind, language)
    proposed.update(await proposed_body(db, row, kind, language))
    db.rollback()
    row = db.query(model).filter_by(id=entity_id).with_for_update().first()
    if row is None:
        return
    apply_missing(row, proposed)
    if missing(row, kind, language):
        raise ValueError("Generated language content is incomplete")
    mark_actual_languages(row, kind)
    db.commit()


