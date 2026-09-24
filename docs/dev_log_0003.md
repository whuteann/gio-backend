# dev_log_0003 — Subscription & entitlement overhaul

**Status:** Implemented and verified end-to-end (curl + live browser via
`gio-member-app`). Companion to `gio-member-app/docs/dev_log_0003.md`.

## What changed

The user specified 8 concrete free-vs-premium rules for the app. The
previous gating (`app/services/entitlement.py`) only covered a subset, with
different rules:

1. **Progress trend** (weekly free / monthly premium) — already correct,
   no change.
2. **Check-in history** — was a row-count cap (last 3 vs unlimited); now a
   **7-day rolling window** for free (`check_in_history_cutoff`), unlimited
   for premium/trial.
3. **Colour reasoning + "pattern"** — free sees a brief reasoning line and
   only today's colour; premium sees the full reasoning set and a new
   `GET /recommendations` list endpoint (the "pattern"/colour-history view).
   The brief-vs-in-depth text split was actually a frontend concern (see the
   frontend's dev log) — the backend's only addition here is the list
   endpoint.
4. **Inner Reading depth** — free gets a ~100-word narrative; premium gets
   the full narrative plus a new 4-area breakdown (Work / Relationships /
   Personal Growth / Conflict Management). Depth-gated **at read time, not
   write time** (`reading_content_for_plan` in `app/services/scoring.py`),
   so upgrading to Premium retroactively unlocks full depth on readings
   taken while on the free plan — same live-gating philosophy the trend
   chart already used.
5. **Inner Reading frequency** — was "1 free reading, ever"
   (`first_free_reading_consumed_at`); now **3 free per rolling 7 days**
   (`inner_reading_weekly_count`, a live COUNT query, same pattern already
   used for `readings_count` in `app/services/cascade.py`).
6. **Check-in submission unlimited for both plans** — already correct, no
   change.
7. **7-day free trial** — new, **opt-in** (`POST /subscription/start-trial`,
   not automatic at registration). Adds `Subscription.trial_ends_at`; once
   set it's never cleared, so its mere presence (even after the 7 days have
   lapsed) means "trial already used" — no separate flag needed.
   `is_premium_active` checks it first, before plan/status, computed live
   from the timestamp with no cron job — the same style already used for the
   `CANCELLED` + `expires_at` grace period.
8. **Single RM19.90/month plan** — `billing_cycle` removed entirely from the
   `Subscription` model and `SubscribeRequest`/`SubscriptionOut`; `POST
   /subscription/subscribe` takes no body, always a 30-day cycle.

## Schema changes

`Subscription`: dropped `billing_cycle` and `first_free_reading_consumed_at`,
added `trial_ends_at` (nullable, timezone-aware). Migration:
`alembic/versions/ee09635a3ec5_subscription_trial_and_weekly_gating.py`.

`app/schemas/subscription.py` (the old `SubscribeRequest`) was deleted —
subscribing takes no request body now.

## New/changed endpoints

- `POST /subscription/start-trial` — 400 if already Premium or already used
  a trial; otherwise sets `trial_ends_at = now + 7 days`.
- `GET /recommendations` — new list endpoint; free gets `.limit(1)` (today's
  colour only), premium gets the full history, ordered `generated_at.desc()`.
- `GET /check-ins`, `POST /inner-readings`, `GET /inner-readings`,
  `GET /inner-readings/{id}` — all rewired to the new entitlement functions
  (see `app/services/entitlement.py`, rewritten this pass).

`InnerReadingOut` gained `life_area_insights` (`dict[str, str] | None`) and
`is_premium_content` (`bool`), populated per-request by
`readings.py::_serialize()`.

## What was tested

Curl pass against the live Docker backend: registered a user, submitted 3
Inner Readings (succeeds), 4th returns 403 with the new copy; `POST
/subscription/start-trial` flips `is_premium_active` true immediately (4th
reading now succeeds); a second `start-trial` call 400s ("already used");
`POST /subscription/subscribe` with an empty body → Premium, 30-day
`renews_at`; fetched the same reading detail before and after upgrading to
Premium — narrative word count and `life_area_insights` flipped from
truncated/null to full/populated on the *same* reading row, confirming the
retroactive-unlock behavior; `GET /recommendations` returned 1 item free vs
full history premium; check-in submission confirmed unlimited on a free
account (5 submitted, all accepted, all returned within the 7-day window).

Then a full live Playwright pass through `gio-member-app` (registered →
onboarded → hit the weekly reading cap → started trial → confirmed the gate
lifted without re-login → confirmed in-depth reading content appeared →
confirmed the colour-history section appeared) — 13/13 checks passed. See
the frontend's dev log for the page-by-page detail.
