#!/usr/bin/env python3
"""Compatibility entry point for reading-language repair.

The repair now supports en/zh/ms and checks actual fields, including older
READY rows. It defaults to dry-run; writing requires --apply --yes-production.
Use backfill_content_languages.py directly to repair personality results too.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backfill_content_languages import main

if __name__ == "__main__":
    if "--kind" not in sys.argv:
        sys.argv.extend(["--kind", "readings"])
    raise SystemExit(main())
