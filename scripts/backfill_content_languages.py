#!/usr/bin/env python3
"""Repair missing reading/personality languages, including pre-Malay READY rows.

Defaults to a read-only inventory. Writing requires --apply --yes-production.
One model call per incomplete generated body; each row commits independently.
Existing text, scores, dates, and the primary language are never overwritten.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


async def run(args) -> int:
    import app.models  # noqa: F401 — register all mapper relationships
    from app.database import SessionLocal
    from app.models.personality import CorePersonality
    from app.models.reflection import InnerReading

    db = SessionLocal()
    models = {"readings": InnerReading, "personalities": CorePersonality}
    jobs = []
    try:
        for kind, model in models.items():
            if args.kind not in ("all", kind):
                continue
            order = model.created_at if kind == "readings" else model.generated_at
            query = db.query(model).order_by(order.asc(), model.id.asc())
            if args.user_id:
                query = query.filter(model.user_id == args.user_id)
            for row in query.all():
                proposed = catalog_copy(row, kind, args.language)
                if missing(row, kind, args.language) or any(
                    value and not getattr(row, name, None) for name, value in proposed.items()
                ):
                    jobs.append((kind, row.id))
        print(f"{len(jobs)} row(s) need {args.language}; no content text is printed.")
        jobs = jobs[:args.limit]
        for kind, row_id in jobs:
            print(f"  {kind}: {row_id}")
        if not args.apply:
            print("DRY RUN: no model calls or database writes. Use --apply --yes-production to repair.")
            return 0

        failed = 0
        for kind, row_id in jobs:
            try:
                row = db.get(models[kind], row_id)
                if row is None:
                    continue
                proposed = catalog_copy(row, kind, args.language)
                proposed.update(await proposed_body(db, row, kind, args.language))
                # Discard the generator's in-memory assignments and refresh
                # from a locked row before filling ONLY still-empty fields.
                db.rollback()
                row = db.query(models[kind]).filter_by(id=row_id).with_for_update().first()
                if row is None:
                    continue
                apply_missing(row, proposed)
                mark_actual_languages(row, kind)
                db.commit()
                print(f"  repaired {kind}: {row_id}")
            except Exception as exc:
                db.rollback()
                failed += 1
                print(f"  FAILED {kind}: {row_id} ({type(exc).__name__}); unchanged", file=sys.stderr)
        print(f"{len(jobs) - failed} repaired, {failed} failed. Re-run dry-run to inspect remaining rows.")
        return int(failed > 0)
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=SUPPORTED, default="ms")
    parser.add_argument("--kind", choices=("all", "readings", "personalities"), default="all")
    parser.add_argument("--user-id", type=uuid.UUID)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes-production", action="store_true")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.apply and (args.dry_run or not args.yes_production):
        parser.error("Writing requires --apply --yes-production without --dry-run")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
