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
from app.services.content_languages import (
    READING_FIELDS, PERSONALITY_FIELDS, column, missing, apply_missing,
    mark_actual_languages, catalog_copy, proposed_body,
)


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
