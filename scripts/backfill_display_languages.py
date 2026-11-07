"""Fill missing historical Malay display copy; never overwrite an existing value."""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def run(apply=False):
    import app.models
    from app.database import SessionLocal
    from app.models.reflection import InnerReading, InnerStateSnapshot, CheckInSession
    from app.models.recommendation import RecommendationProfile, RecommendationItem
    from app.services.content_translation import translate_texts
    scalar_fields = {
        InnerReading: ("insight", "reflection_question", "current_focus", "result_summary"),
        InnerStateSnapshot: ("summary",),
        CheckInSession: ("title", "subtitle"),
        RecommendationProfile: ("current_focus", "summary", "letter"),
        RecommendationItem: ("title", "reason"),
    }
    targets = []
    with SessionLocal() as db:
        for model, fields in scalar_fields.items():
            for row in db.query(model).order_by(model.id).all():
                for field in fields:
                    column = field + "_ms"
                    if not hasattr(model, column) or getattr(row, column):
                        continue
                    source = getattr(row, field, None) or getattr(row, field + "_en", None) or getattr(row, field + "_zh", None)
                    if isinstance(source, str) and source.strip():
                        targets.append((model, row.id, column, False, source))
        for row in db.query(InnerStateSnapshot).order_by(InnerStateSnapshot.id).all():
            for field in ("insight", "reflection_question", "reminder", "current_focus", "friendly_advice", "affirmation"):
                value = getattr(row, field)
                if isinstance(value, dict) and not value.get("ms"):
                    source = value.get("en") or value.get("zh")
                    if source:
                        targets.append((InnerStateSnapshot, row.id, field, True, source))
    print(f"{len(targets)} missing Malay display field(s). No source text printed.", flush=True)
    if not apply:
        print("DRY RUN: no model calls or writes.")
        return
    for offset in range(0, len(targets), 20):
        batch = targets[offset:offset + 20]
        translated = await translate_texts({str(i): value[4] for i, value in enumerate(batch)}, "ms")
        with SessionLocal() as db:
            for i, (model, row_id, column, is_json, _) in enumerate(batch):
                row = db.query(model).filter_by(id=row_id).with_for_update().first()
                if row is None:
                    continue
                current = getattr(row, column)
                if is_json:
                    if isinstance(current, dict) and not current.get("ms"):
                        setattr(row, column, {**current, "ms": translated[str(i)]})
                elif not current:
                    setattr(row, column, translated[str(i)])
            db.commit()
        print(f"Repaired batch {offset + 1}-{min(offset + 20, len(targets))}.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes-production", action="store_true")
    args = parser.parse_args()
    if args.apply and not args.yes_production:
        parser.error("Writing requires --apply --yes-production")
    asyncio.run(run(args.apply))
