#!/usr/bin/env python3
"""Create a fully onboarded Auren account from the command line.

Simulates the whole user-creation + onboarding path in one shot:

  1. signup           -> services.auth.create_user (User + FREE Subscription)
  2. onboarding       -> numerology from the birthdate, then the AI Core
                         Personality narrative in BOTH languages
  3. premium (opt-in) -> subscription_payment._apply_premium + a COMPLETED
                         SubscriptionPayment row, YEARLY cycle

Every step calls the same functions the real API endpoints call, so this
script cannot drift from production signup behaviour. What it deliberately
does NOT do is reach Xendit: `--premium` writes the paid state directly,
the same shape the PAYMENT_GATEWAY_ENABLED=false bypass produces. No
invoice, no money, no live payment-gateway call.

It is also more atomic than the real flow. The API creates the user in one
request (POST /auth/register) and the Core Personality in another
(POST /core-personality/calculate), so a failure between them leaves a
signed-up user stuck at the birthdate step. Here everything is one
transaction: if the OpenAI call fails, nothing is written at all.

Run it inside the app container, where DATABASE_URL and OPENAI_API_KEY are
already set:

    docker compose exec app python scripts/create_account.py \\
        --display-name "Mark" \\
        --phone 60123456789 \\
        --password "SomePassword123" \\
        --birthdate 1992-07-14 \\
        --premium

Add --yes-production when the target really is the live database.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

# Allow `python scripts/create_account.py` from the repo root as well as
# from inside scripts/ — the container's WORKDIR is /app, but don't depend
# on the caller's cwd for something this easy to make robust.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models  # noqa: F401,E402 — register every mapper before first use (see app/main.py)
from app.config import settings  # noqa: E402
from app.core.security import create_access_token, create_refresh_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.payment import SubscriptionPayment  # noqa: E402
from app.models.personality import CorePersonality  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.auth import RegisterRequest  # noqa: E402
from app.services.account_link import notify_bracelet_backend_of_signup  # noqa: E402
from app.services.ai_personality import generate_core_personality_content  # noqa: E402
from app.services.auth import create_user  # noqa: E402
from app.services.content import PREMIUM_PRICING  # noqa: E402
from app.services.numerology import (  # noqa: E402
    calculate_birthday_number,
    calculate_colour_weights,
    calculate_life_path_number,
    calculate_talent_number,
)
# Private by name, imported on purpose: this is the one definition of "what
# being Premium means" (plan/status/renews_at/expires_at/cancelled_at), and
# duplicating it here is exactly how a script like this goes stale.
from app.services.subscription_payment import _apply_premium  # noqa: E402

BILLING_CYCLE = "YEARLY"
LANGUAGES = ("en", "zh")

GREEN, YELLOW, RED, BOLD, DIM, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[2m", "\033[0m"


def _c(text: str, colour: str) -> str:
    return f"{colour}{text}{RESET}" if sys.stdout.isatty() else text


# --------------------------------------------------------------------------
# input validation
# --------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Create a fully onboarded Auren account (signup + Core Personality + optional Premium).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--display-name", required=True, help="The user's display name.")
    p.add_argument("--phone", required=True, help="Login identity: 8-15 digits, no '+', spaces or dashes.")
    p.add_argument("--password", required=True, help="Plaintext password; stored bcrypt-hashed.")
    p.add_argument("--birthdate", required=True, help="YYYY-MM-DD — drives the whole Core Personality.")
    p.add_argument("--premium", action="store_true",
                   help=f"Grant Premium ({BILLING_CYCLE.lower()}) with no payment collected. Omit for a FREE account.")
    p.add_argument("--email", default=None, help="Optional. Only used for Xendit invoicing; not a login identity.")
    p.add_argument("--language", default="en", choices=["en", "zh"],
                   help="Primary language of the account (default: en). Both languages are generated either way.")
    p.add_argument("--with-tokens", action="store_true",
                   help="Also print a ready-to-use access/refresh token pair for curl.")
    p.add_argument("--notify-bracelet", action="store_true",
                   help="Fire the braceletBackend signup-sync webhook, as POST /auth/register does. "
                        "Off by default: against production this writes a mirror row into braceletBackend's live database.")
    p.add_argument("--yes-production", action="store_true",
                   help="Required confirmation when the target looks like the production database.")
    return p.parse_args()


def validate(args: argparse.Namespace) -> date:
    """Validate through the API's own request schema, so the rules here are
    the rules the real endpoint enforces — phone pattern, email format and
    all. Returns the parsed birthdate."""
    try:
        RegisterRequest(
            phone_number=args.phone,
            password=args.password,
            display_name=args.display_name,
            language=args.language,
            email=args.email,
        )
    except Exception as e:  # pydantic ValidationError
        die(f"Invalid input, same rules as POST /auth/register:\n{e}")

    if not args.display_name.strip():
        die("--display-name cannot be blank.")

    try:
        birthdate = date.fromisoformat(args.birthdate)
    except ValueError:
        die(f"--birthdate must be YYYY-MM-DD, got {args.birthdate!r}")

    today = date.today()
    if birthdate > today:
        die(f"--birthdate {birthdate} is in the future.")
    if birthdate.year < 1900:
        die(f"--birthdate {birthdate} is implausible (before 1900).")
    return birthdate


def die(message: str, code: int = 1) -> None:
    print(f"\n{_c('FAILED', RED)}  {message}\n", file=sys.stderr)
    sys.exit(code)


# --------------------------------------------------------------------------
# environment detection
# --------------------------------------------------------------------------

def detect_production() -> str | None:
    """Return a human-readable reason this is the production database, or
    None if it isn't.

    Getting this right is harder than it looks, and two obvious signals are
    both useless here:

    - DATABASE_URL is identical in both environments (`db:5432/gio`), since
      each resolves that name on its own compose network.
    - App config doesn't distinguish them either. Local dev on this project
      is configured to point at the *real* braceletBackend, a vercel.app
      origin and the same live `xnd_production_` Xendit key, so sniffing
      CORS_ORIGINS / BRACELET_BACKEND_URL / XENDIT_SECRET_KEY flags a
      laptop as production. That was tried and discarded.

    What does distinguish them is where the code is running: the EC2
    instance-metadata endpoint is reachable from a container on the box and
    not from one on a developer machine (verified both ways — ~1s timeout
    locally, immediate connect on EC2). `GIO_ENV` overrides the probe if it
    is ever set explicitly.
    """
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


# --------------------------------------------------------------------------
# the work
# --------------------------------------------------------------------------

async def generate_both_languages(birthdate_str: str, numbers: dict, colour_weights: dict):
    """Both languages concurrently. The API generates the primary inline and
    the other in a BackgroundTask (core_personality.py::_generate_secondary_language);
    a script has nowhere to defer to, so it waits for both and lands directly
    on generation_status=READY instead of PARTIAL."""
    results = await asyncio.gather(*[
        generate_core_personality_content(
            birthdate=birthdate_str,
            birthday_number=numbers["birthday"],
            life_path_number=numbers["life_path"],
            talent_number=numbers["talent"],
            colour_weights=colour_weights,
            language=language,
        )
        for language in LANGUAGES
    ])
    return dict(zip(LANGUAGES, results))


def build_core_personality(user: User, primary_language: str, numbers: dict,
                           colour_weights: dict, content_by_language: dict) -> CorePersonality:
    personality = CorePersonality(
        id=uuid.uuid4(),
        user_id=user.id,
        primary_language=primary_language,
        # Both languages are present by the time this is committed, which is
        # the state the API only reaches after its background task finishes.
        generation_status="READY",
        birthday_number=numbers["birthday"],
        life_path_number=numbers["life_path"],
        talent_number=numbers["talent"],
        scarlet_score=colour_weights["scarlet"],
        russet_score=colour_weights["russet"],
        gold_score=colour_weights["gold"],
        forest_score=colour_weights["forest"],
        ocean_score=colour_weights["ocean"],
    )
    for language, content in content_by_language.items():
        setattr(personality, f"title_{language}", content.title)
        setattr(personality, f"subtitle_{language}", content.subtitle)
        setattr(personality, f"overview_{language}", content.overview)
        setattr(personality, f"birthday_number_points_{language}", [p.model_dump() for p in content.birthday_number_points])
        setattr(personality, f"life_path_number_points_{language}", [p.model_dump() for p in content.life_path_number_points])
        setattr(personality, f"talent_number_points_{language}", [p.model_dump() for p in content.talent_number_points])
        setattr(personality, f"summary_{language}", content.summary)
    return personality


def grant_premium(db, user: User, now: datetime) -> SubscriptionPayment:
    """Mirrors subscription_payment._bypass_checkout: the real paid state
    transition plus a COMPLETED payment row, so entitlement checks, the
    billing-history endpoint and the invoice PDF all behave exactly as they
    do for a genuinely paid account. The reference_no is marked SCRIPT so
    these are distinguishable from both real and bypass payments later."""
    pricing = PREMIUM_PRICING[BILLING_CYCLE]
    payment = SubscriptionPayment(
        id=uuid.uuid4(),
        user_id=user.id,
        billing_cycle=BILLING_CYCLE,
        amount=pricing["amount"],
        currency=pricing["currency"],
        xendit_invoice_id=None,
        reference_no=f"GIO-SUB-SCRIPT-{uuid.uuid4()}",
        status="COMPLETED",
        invoice_url=None,
        provider_data={
            "script": True,
            "reason": "created by scripts/create_account.py --premium",
            "no_payment_collected": True,
        },
        paid_at=now,
    )
    db.add(payment)
    _apply_premium(db, user, BILLING_CYCLE, now)
    return payment


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------

def print_result(args, user: User, personality: CorePersonality, premium: bool, tokens: tuple[str, str] | None) -> None:
    sub = user.subscription
    rule = "=" * 68

    print()
    print(_c(rule, GREEN))
    print(_c(f"  SUCCESS — account created and onboarded", f"{BOLD}{GREEN}"))
    print(_c(rule, GREEN))
    print()
    print(_c("  LOG IN WITH THESE CREDENTIALS", BOLD))
    print(f"    Phone number   : {_c(user.phone_number, BOLD)}")
    print(f"    Password       : {_c(args.password, BOLD)}")
    print()
    print(_c("  ACCOUNT", BOLD))
    print(f"    Display name   : {user.display_name}")
    print(f"    Gio ID         : {user.gid}")
    print(f"    User ID        : {user.id}")
    print(f"    Email          : {user.email or _c('(none)', DIM)}")
    print(f"    Language       : {user.preferred_language}")
    print(f"    Birthdate      : {user.birthdate}")
    print(f"    Onboarded at   : {user.onboarding_completed_at:%Y-%m-%d %H:%M:%S} UTC")
    print()
    print(_c("  SUBSCRIPTION", BOLD))
    plan_line = f"{sub.plan} / {sub.status}"
    print(f"    Plan           : {_c(plan_line, GREEN if premium else DIM)}")
    if premium:
        print(f"    Renews at      : {sub.renews_at:%Y-%m-%d} "
              f"{_c(f'({BILLING_CYCLE.lower()}, no payment collected)', DIM)}")
    print()
    print(_c("  CORE PERSONALITY", BOLD))
    primary = personality.primary_language
    other = "zh" if primary == "en" else "en"
    print(f"    Title ({primary})     : {getattr(personality, f'title_{primary}')}")
    print(f"    Title ({other})     : {getattr(personality, f'title_{other}')}")
    print(f"    Subtitle       : {getattr(personality, f'subtitle_{primary}')}")
    print(f"    Numbers        : birthday {personality.birthday_number} | "
          f"life path {personality.life_path_number} | talent {personality.talent_number}")
    print(f"    Colours        : scarlet {personality.scarlet_score} | russet {personality.russet_score} | "
          f"gold {personality.gold_score} | forest {personality.forest_score} | ocean {personality.ocean_score}")
    print(f"    Status         : {personality.generation_status} {_c('(both languages present)', DIM)}")

    if tokens:
        access, refresh = tokens
        print()
        print(_c("  TOKENS", BOLD))
        print(f"    Access  ({settings.access_token_expire_minutes}m) : {access}")
        print(f"    Refresh ({settings.refresh_token_expire_days}d)  : {refresh}")

    print()
    print(_c(rule, GREEN))
    print()


# --------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    birthdate = validate(args)

    production_reason = detect_production()
    if production_reason:
        print(f"\n{_c('PRODUCTION TARGET', f'{BOLD}{YELLOW}')} — {production_reason}")
        if not args.yes_production:
            die("Refusing to write to the production database without --yes-production.\n"
                "        Re-run with that flag if this is intentional.")
        print(f"  {_c('--yes-production given, proceeding.', YELLOW)}")

    if args.notify_bracelet:
        print(f"{_c('..', DIM)} --notify-bracelet will POST to {settings.bracelet_backend_url}")

    if not settings.openai_api_key:
        die("OPENAI_API_KEY is empty — the Core Personality narrative cannot be generated.")

    db = SessionLocal()
    try:
        phone = args.phone.strip()
        if db.query(User).filter(User.phone_number == phone).first():
            die(f"An account with phone number {phone} already exists "
                f"(POST /auth/register would return 409 here).")

        # 1. Signup, exactly as POST /auth/register does it.
        user = create_user(
            db, phone_number=phone, password=args.password,
            display_name=args.display_name.strip(), language=args.language, email=args.email,
        )

        # 2. Onboarding. Numerology is deterministic and local; only the
        #    narrative needs the model.
        numbers = {
            "birthday": calculate_birthday_number(args.birthdate),
            "life_path": calculate_life_path_number(args.birthdate),
            "talent": calculate_talent_number(args.birthdate),
        }
        colour_weights = calculate_colour_weights(
            args.birthdate, numbers["birthday"], numbers["life_path"], numbers["talent"],
        )
        print(f"{_c('..', DIM)} numerology: birthday {numbers['birthday']}, "
              f"life path {numbers['life_path']}, talent {numbers['talent']}")
        print(f"{_c('..', DIM)} generating Core Personality in {' + '.join(LANGUAGES)} "
              f"via {settings.openai_model} (this takes a moment)")

        content_by_language = asyncio.run(generate_both_languages(args.birthdate, numbers, colour_weights))

        personality = build_core_personality(user, args.language, numbers, colour_weights, content_by_language)
        db.add(personality)

        now = datetime.now(timezone.utc)
        user.birthdate = birthdate
        # Same rule as the calculate endpoint: onboarding is complete the
        # moment the Core Personality exists.
        user.onboarding_completed_at = now

        # 3. Premium, if asked for.
        if args.premium:
            grant_premium(db, user, now)
            print(f"{_c('..', DIM)} granted Premium ({BILLING_CYCLE.lower()}), no payment collected")

        # One commit for the whole account — see the module docstring.
        db.commit()
        db.refresh(user)
        db.refresh(personality)

        tokens = None
        if args.with_tokens:
            tokens = (create_access_token(str(user.id)), create_refresh_token(str(user.id)))

        # After the commit, never before: this is a side effect on another
        # service, and it must not be able to roll this account back.
        if args.notify_bracelet:
            print(f"{_c('..', DIM)} notifying braceletBackend of the signup")
            notify_bracelet_backend_of_signup(user)

        # Last, so the credentials are the final thing on screen.
        print_result(args, user, personality, args.premium, tokens)

    except SystemExit:
        raise
    except Exception as e:
        db.rollback()
        die(f"{type(e).__name__}: {e}\n        Rolled back — no account was created.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
