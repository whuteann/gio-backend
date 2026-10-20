#!/usr/bin/env python3
"""Generate the missing second language for Inner Readings stuck at PARTIAL.

Every reading written before migration c7f2b9a04d31 was English-only, and
any reading whose background pass failed is in the same state. Both show up
as `generation_status = 'PARTIAL'`. This fills in the other language and
flips them to READY.

The generation is the same function the live request path uses
(services/reading_language.py), so a backfilled reading is indistinguishable
from one generated at submit time.

    # see what would happen, no API calls, no writes
    docker compose exec app python scripts/backfill_reading_language.py --dry-run

    # do it, oldest first, stopping after 10
    docker compose exec app python scripts/backfill_reading_language.py --limit 10

**This costs money** — one model call per reading. Check --dry-run's count
first. Safe to interrupt and safe to re-run: each reading is committed on its
own, and a finished one is no longer PARTIAL so it is never picked up twice.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models  # noqa: F401,E402 — register every mapper first (see app/main.py)
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.reflection import InnerReading  # noqa: E402
from app.services.reading_language import OTHER_LANGUAGE, fill_secondary_language  # noqa: E402

GREEN, YELLOW, RED, BOLD, DIM, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[2m", "\033[0m"


def _c(text: str, colour: str) -> str:
    return f"{colour}{text}{RESET}" if sys.stdout.isatty() else text


def detect_production() -> str | None:
    """Same probe as scripts/create_account.py: app config is identical in
    both environments, but the EC2 metadata endpoint is only reachable from
    a container on the box."""
    declared = os.environ.get("GIO_ENV", "").strip().lower()
    if declared:
        return f"GIO_ENV={declared}" if declared in ("production", "prod") else None
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.connect(("169.254.169.254", 80))
        return "running on EC2 (instance metadata endpoint is reachable)"
    except OSError:
        return None
    finally:
        sock.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fill in the missing second language for PARTIAL Inner Readings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--dry-run", action="store_true",
                   help="List what would be generated and stop. No API calls, no writes.")
    p.add_argument("--limit", type=int, default=None,
                   help="Process at most this many readings. Oldest first, so repeated runs make progress.")
    p.add_argument("--yes-production", action="store_true",
                   help="Required confirmation when the target looks like the production database.")
    return p.parse_args()


async def run(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        query = (
            db.query(InnerReading)
            .filter(InnerReading.generation_status != "READY")
            .order_by(InnerReading.created_at.asc())
        )
        total = query.count()
        readings = query.limit(args.limit).all() if args.limit else query.all()

        if not readings:
            print(f"\n{_c('Nothing to do', GREEN)} — every Inner Reading is already READY.\n")
            return 0

        print(f"\n{total} reading(s) not READY; this run will process {len(readings)}.\n")
        for r in readings:
            primary = r.primary_language or "en"
            print(f"  {str(r.id)[:8]}…  {r.created_at:%Y-%m-%d}  has {primary} -> needs {OTHER_LANGUAGE[primary]}")

        if args.dry_run:
            print(f"\n{_c('Dry run', YELLOW)} — nothing generated, nothing written.\n")
            return 0

        if not settings.openai_api_key:
            print(f"\n{_c('FAILED', RED)}  OPENAI_API_KEY is empty — nothing can be generated.\n", file=sys.stderr)
            return 1

        print(f"\n{_c('..', DIM)} generating via {settings.openai_model}, one call per reading\n")
        done = failed = 0
        for i, reading in enumerate(readings, 1):
            primary = reading.primary_language or "en"
            target = OTHER_LANGUAGE[primary]
            label = f"[{i}/{len(readings)}] {str(reading.id)[:8]}… {primary}->{target}"
            # Committed one at a time, so an interrupt keeps everything done
            # so far and a crash costs at most the reading in flight.
            if await fill_secondary_language(db, reading, target):
                db.commit()
                done += 1
                print(f"  {_c('ok  ', GREEN)} {label}  {reading.title or reading.title_zh}")
            else:
                db.rollback()
                failed += 1
                print(f"  {_c('fail', RED)} {label}  (left PARTIAL, see the logged exception)")

        remaining = db.query(InnerReading).filter(InnerReading.generation_status != "READY").count()
        print(f"\n{_c('Done', GREEN)} — {done} generated, {failed} failed, {remaining} still PARTIAL.\n")
        return 0 if failed == 0 else 1
    finally:
        db.close()


def main() -> int:
    args = parse_args()
    reason = detect_production()
    if reason:
        print(f"\n{_c('PRODUCTION TARGET', f'{BOLD}{YELLOW}')} — {reason}")
        if not args.dry_run and not args.yes_production:
            print(f"\n{_c('FAILED', RED)}  Refusing to write to the production database without "
                  f"--yes-production.\n        (--dry-run needs no flag.)\n", file=sys.stderr)
            return 1
        if not args.dry_run:
            print(f"  {_c('--yes-production given, proceeding.', YELLOW)}")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
