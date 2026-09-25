# behaviour_log_0009 — Xendit payment gateway: real Premium checkout (sandbox)

**Status:** Implemented and verified (all 5 phases + the invoice-history
addition). One caveat: `XENDIT_SECRET_KEY` is not yet set to a real
Xendit test key in this environment, so `POST /subscription/checkout`'s
actual call to Xendit fails at Xendit's own authentication boundary — see
"Verification" at the bottom for exactly what was and wasn't exercised
live, and what a real key would additionally confirm. Outlines how to replace
`POST /subscription/subscribe`'s current no-payment, direct-grant behavior
(`database_audit_2026-09-23.md` finding F5) with a real Xendit-backed
checkout for monthly/yearly Premium, using
`GioMembershipPlatform/xendit-handover/` as the proven reference
implementation (a working Xendit **Invoices API** integration already
running in `braceletBackend`). This document adapts a *working
ecommerce-order* pattern to Gio's *subscription* model — Gio has no cart/
order concept at all, by design, so the adaptation has real decision
points, not just a copy-paste. Pricing, currency, invoice visibility, and
the renewal model are now confirmed (see "How the open questions were
resolved" below); remaining open items are narrow and don't block
starting Phase 1.

## How the open questions were resolved

1. **Pricing** — RM19.90/month (currency: **MYR**, matching the
   reference's own default — a real confirmation, not an assumption
   carried over). One yearly package, discounted 20% off 12 months paid
   monthly: `19.90 × 12 × 0.80 = 191.04`. `PREMIUM_PRICING` in Phase 3
   below uses these two real numbers, not placeholders.
2. **No auto-renewal, confirmed** — "when it expires, it just expires...
   want to resubscribe, they'll have to pay." Matches this plan's
   original assumption exactly (Xendit's Invoices API is one-shot, not a
   recurring-charge product) — now explicit product intent, not just an
   API limitation being worked around.
3. **`POST /subscription/subscribe` (the free, no-payment grant) is
   replaced, not kept alongside the real flow** — "when user press
   subscribe, then charge them" describes one single flow. This endpoint
   is removed once `/checkout` works (Phase 3).
4. **New requirement surfaced, not in the original plan**: invoices must
   be **viewable within the platform** — "issue an invoice... that can be
   viewed within the platform because visibility." This adds a read
   endpoint + a frontend billing-history view to Phase 5, not just the
   Subscribe-button wiring originally scoped.
5. **No cancellations, no refunds — at all.** No Xendit refund API call
   is ever built, in any phase. `POST /subscription/cancel` (mid-cycle
   downgrade) is out of scope for this integration entirely, not just
   "untouched" — a paid subscription's only end state is expiry, matching
   point 2 above. Nothing in this plan calls, or needs to call, a refund
   endpoint.
6. **Yearly price displayed as the flat charged amount, full stop** —
   `RM191.04`, no "effective RM15.92/mo" framing, no per-month
   breakdown anywhere in the checkout UI. Show what's actually charged.
7. **Invoice history: simple and printable.** A plain list (date, cycle,
   amount, status — no extra dashboard chrome), rendered so the browser's
   native print (`window.print()` + print-specific CSS, e.g. hiding nav
   chrome/buttons in the print stylesheet) produces a usable paper/PDF
   record. No PDF-generation service, no emailed receipts — the printable
   HTML view *is* the receipt.

Nothing left open that blocks starting Phase 1.

## Objectives (mapped to the three success criteria given)

1. **Xendit infrastructure + services, env-var driven credentials** — a
   `services/xendit_client.py` (or similarly-scoped module) owning all
   direct Xendit API calls, config loaded from environment variables
   (`app/config.py`, matching this app's existing `Settings` pattern —
   see `openai_api_key`/`openai_model` for precedent), no secret ever
   hardcoded or committed.
2. **Sandbox by default** — Xendit doesn't have a separate sandbox
   *hostname* the way the handover's other provider (Fiuu) does
   (`FIUU_ENVIRONMENT` switches `sandbox.fiuu.com` vs `fiuu.com`).
   Xendit's test/live split is **which secret key you configure**
   (`xnd_development_...` vs `xnd_production_...`) against the *same*
   `https://api.xendit.co` base URL — confirmed from the handover's own
   `_xendit_auth()`/`XENDIT_BASE_URL`, which never branches on an
   environment flag. "Sandbox" for this integration means: `.env` holds a
   **test-mode secret key**, full stop — see open question 1 for how this
   should still be made explicit/visible in the codebase.
3. **An initiate endpoint wired to the frontend Subscribe button,
   producing a real (sandbox-mode) Xendit invoice** — `POST
   /subscription/checkout` returning an `invoice_url`, replacing
   `membership.tsx`'s current direct `subscribe()` call.

## What's being reused vs. what's genuinely different

The handover's flow is sound and directly portable: **lock the paying
row → check for a reusable pending payment → call `POST /v2/invoices` →
persist the invoice → webhook settles on `PAID`/`SETTLED`/`EXPIRED`,
verifying the paid amount before trusting it**. That whole shape carries
over. What doesn't carry over, because Gio has no equivalent concept:

- **No `Order`.** The reference's `Payment` row hangs off an `Order`
  (cart, items, inventory reservation, a payable total already computed
  elsewhere). Gio has no cart/order — the "thing being paid for" is
  simply "this user wants N months of Premium." A new, much smaller
  `SubscriptionPayment` table is this integration's `Order`+`Payment`
  collapsed into one row (see Phase 1) — there's nothing here to reserve
  or release.
- **No inventory locking, but the same duplicate-invoice race exists.**
  The handover's `with_for_update()` on the order row exists so two rapid
  "Pay" taps don't create two Xendit invoices. Gio needs the same
  protection, just locking the user's own pending-payment row instead of
  an order row.
- **Pricing must be invented.** The reference reads `order.total_price`,
  already computed by the cart. Gio has no price for Premium anywhere in
  the codebase today — `subscribe()` just flips a flag. This plan needs
  actual monthly/yearly amounts (open question 2).
- **Settlement target is `Subscription`, not `Order`.** On a paid
  webhook, this integration should reproduce
  `subscription.py::subscribe()`'s existing state transition
  (`plan=PREMIUM`, `status=ACTIVE`, `starts_at`, `renews_at`,
  `expires_at=None`, `cancelled_at=None`) — but now billing-cycle-aware
  (`renews_at = now + 30d` monthly, `+365d` yearly) and gated on the
  webhook actually firing, not granted on request.
- **No true recurring billing in this plan.** The handover only
  demonstrates Xendit's **Invoices API** — a one-shot payment link, not
  an auto-charging subscription product (Xendit has a separate Recurring
  Payments API, not present anywhere in the handover material, so not
  assumed here). This plan is a **manually-renewed checkout**: a Premium
  user due for renewal comes back through the same `/checkout` endpoint
  and pays again. Automatic renewal charges are explicitly out of scope
  — flagging this now so it isn't discovered as a surprise gap later,
  same way `behaviour_log_0008.md` flagged the recommendation engine's
  gap up front.
- **No chatbot path, no Fiuu path, no inventory/referral side-effects.**
  Everything in `payment.py`/`endpoints/payment.py` related to
  `chatbot-initiate`, `X-Chatbot-Secret`, referral credit, or the legacy
  Fiuu hosted/seamless/direct/callback/notification routes is not
  relevant to Gio and is not being ported.

## Phase 1 — Database model

New table, not a repurposed/renamed existing one (the handover's own
README flags its `fiuu_transaction_id` naming as legacy baggage worth
avoiding — Gio has no such legacy, so this starts clean):

**`subscription_payments`**
- `id` (UUID, PK)
- `user_id` (UUID, FK → `users.id`, `CASCADE`, indexed) — Gio's
  equivalent of the reference's `order_id`; there's no separate "order"
  to hang this off.
- `billing_cycle` (String — `MONTHLY` | `YEARLY`)
- `amount` (Numeric(10,2)), `currency` (String) — see open question 2.
- `xendit_invoice_id` (String, nullable until the Xendit call succeeds)
- `reference_no` (String) — Gio-generated `external_id` sent to Xendit
  as `f"GIO-SUB-{uuid4()}"`, mirroring `generate_payment_reference()`'s
  role.
- `status` (String — `PENDING` | `COMPLETED` | `FAILED` | `EXPIRED`)
- `invoice_url` (String, nullable)
- `provider_data` (JSONB) — full Xendit invoice response, same purpose as
  the reference's `Payment.provider_data`.
- `created_at`, `paid_at` (nullable)

No inventory/reservation columns, no Fiuu-named fields, no `bill_*`
columns duplicating user contact info (read from `user.email`/
`user.display_name` at call time instead, same as the reference reads
from `order.user`).

## Phase 2 — Xendit client service + environment

New `app/services/xendit_client.py`:
- `_xendit_auth()` — `httpx.BasicAuth(settings.xendit_secret_key, "")`,
  identical to the reference's `_xendit_auth()`.
- `create_invoice(*, external_id, amount, currency, payer_email, payer_name, description, success_url, failure_url) -> dict` —
  `POST https://api.xendit.co/v2/invoices`, same payload shape as the
  reference (`external_id`, `amount`, `payer_email`, `description`,
  `invoice_duration`, `customer{given_names,email}`,
  `customer_notification_preference`, `success_redirect_url`,
  `failure_redirect_url`, `currency`). No `mobile_number` — Gio's `User`
  model has no phone field, unlike the reference's `user.phone_no`.
- `get_invoice(invoice_id) -> dict` — `GET /v2/invoices/{id}`, for the
  sync/reconciliation path (Phase 4).
- `httpx`, not currently a Gio backend dependency — needs adding
  (`requirements.txt`; the reference's own `requirements.txt` flags it as
  the one new dependency this integration needs).

**`app/config.py` additions** (mirrors `xendit.env.template`'s naming
exactly, for consistency across the org's codebases):
```
xendit_secret_key: str
xendit_webhook_token: str
xendit_success_redirect_url: str
xendit_failure_redirect_url: str
```
No `XENDIT_ENVIRONMENT` setting — per Objective 2 above, there's nothing
for it to switch. If a visible "sandbox vs live" indicator is wanted
anyway (e.g. for a dashboard banner), see open question 1.

## Phase 3 — Pricing + `POST /subscription/checkout`

- New `content.py::PREMIUM_PRICING` (deterministic, same static-constant
  pattern as `FOCUS_COPY`/`READING_CATEGORY` — pricing is not something
  an AI call or a database row should own):
  ```python
  PREMIUM_PRICING = {
      "MONTHLY": {"amount": Decimal("19.90"), "currency": "MYR"},
      # 12 months at RM19.90, discounted 20%: 19.90 * 12 * 0.80 = 191.04
      "YEARLY": {"amount": Decimal("191.04"), "currency": "MYR"},
  }
  ```
  Real numbers, confirmed above — not placeholders.
- `POST /subscription/checkout` (`app/api/v1/endpoints/subscription.py`),
  body `{"billing_cycle": "MONTHLY" | "YEARLY"}`, authenticated (unlike
  the reference's own `/initiate`, which the handover README explicitly
  flags as *not* having an ownership check — Gio's version should require
  `get_current_user` from the start, not repeat that gap):
  1. Lock any existing `PENDING` `subscription_payments` row for this
     user (`with_for_update()`) — reuse it if the cycle/amount still
     matches (mirrors the reference's existing-pending-payment reuse),
     otherwise mark it `FAILED` and create a new one, exactly mirroring
     `create_xendit_invoice_service`'s race-safe shape.
  2. Call `xendit_client.create_invoice(...)`.
  3. Persist `xendit_invoice_id`/`invoice_url`/`provider_data`, `status=PENDING`.
  4. Return `{invoice_url, payment_id, amount, currency, billing_cycle, status}`.

## Phase 4 — Webhook settlement

- `POST /subscription/webhook/xendit` (**no auth dependency** — Xendit
  calls this directly; protected instead by `x-callback-token` against
  `settings.xendit_webhook_token`, checked unconditionally, unlike the
  reference which only checks the token *if configured* — the handover
  README calls that out as a real risk in every deployed environment;
  Gio's version should refuse to process without a configured token
  rather than silently skip verification).
- `services/subscription_payment.py::handle_xendit_webhook(payload, callback_token)`:
  1. Verify token.
  2. Look up `subscription_payments` by `xendit_invoice_id` (fallback to
     `reference_no` == payload's `external_id`, matching the reference's
     two-step lookup).
  3. `PAID`/`SETTLED` → verify `paid_amount` matches the stored `amount`
     exactly (reference's amount-mismatch guard, ported as-is — this is
     the one check standing between "webhook says paid" and "actually
     grant Premium"), then apply the `Subscription` state transition
     from "What's genuinely different" above, keyed off the payment's own
     `billing_cycle`. Idempotent: if the payment row is already
     `COMPLETED`, no-op (mirrors `xp_transactions`' dedupe-key philosophy
     elsewhere in this codebase, applied here as a status check instead
     of a unique constraint, since a webhook can legitimately be
     redelivered by Xendit).
  4. `EXPIRED` → mark payment `FAILED`. No `Subscription` change — the
     user simply never got upgraded, nothing to roll back.
- `POST /subscription/sync-xendit/{payment_id}` — optional operational
  fallback mirroring `sync_xendit_payment_service`, for a missed webhook
  during sandbox testing. Same "no auth dependency, treat as operational"
  caveat the handover README gives its own version.

## Phase 5 — Frontend (+ Phase 4.5 — invoice visibility, backend)

**New backend piece, added by the "viewable within the platform"
requirement**: `GET /subscription/payments` (authenticated, current user
only) — returns the user's own `subscription_payments` rows, newest
first: `billing_cycle`, `amount`, `currency`, `status`, `invoice_url`,
`created_at`, `paid_at`. This is the invoice history/receipt list, not a
new capability Xendit itself provides — Gio already has the data once
Phase 1's table exists; this is a straightforward read endpoint, same
shape as `GET /check-ins` or `GET /inner-readings`.

- `lib/api/subscription.ts` — new `checkoutSubscription(token, cycle)` →
  `POST /subscription/checkout`, new `listSubscriptionPayments(token)` →
  `GET /subscription/payments` for the billing-history view, and
  `getSubscriptionPaymentStatus` (or reuse polling against
  `GET /subscription`) for the success page.
- **Billing history: simple and printable, confirmed** — a plain list
  on `/membership` (or its own `/membership/billing` page): date, cycle,
  amount, status. No dashboard chrome, no PDF-generation service, no
  emailed receipts. A print stylesheet (hide nav/buttons, keep just the
  list) plus a "Print" button calling `window.print()` is the entire
  printable-receipt mechanism — the browser's own print-to-PDF handles
  the rest. `invoice_url` link included where still reachable (Xendit
  invoice links don't stay valid forever; a dead link is handled
  gracefully, not treated as an error state).
- **`membership.tsx` needs a billing-cycle control it doesn't have
  today** — currently `subscribe()` takes no parameters at all; there is
  no monthly/yearly UI anywhere in the app right now. Adding one (a
  simple two-button toggle before "Subscribe") is in scope, not a
  pre-existing piece being rewired. The yearly option shows **RM191.04
  flat** — the actual charged amount, nothing else. No "RM15.92/mo
  effective" framing, no per-month breakdown anywhere near it.
- Subscribe button: `checkoutSubscription(token, cycle)` →
  `window.location.href = result.invoice_url` (matches the reference
  frontend guide's own recommended pattern — no custom payment form,
  Xendit's hosted checkout page handles card/e-wallet/bank entry).
- New `/membership/payment-success` and `/membership/payment-failed`
  pages (or reuse a single result page keyed by query param) as the
  configured `xendit_success_redirect_url`/`xendit_failure_redirect_url`
  targets — read-only, they just re-fetch `GET /subscription` to reflect
  whatever the webhook already settled server-side. **Never treat the
  redirect itself as proof of payment** — the handover README states this
  explicitly and the reference code follows it; only the webhook (or the
  sync fallback) actually grants Premium.

## Open questions

All resolved during review — pricing/currency, no auto-renewal, removing
the free-grant endpoint, invoice visibility, no cancellations/refunds,
flat yearly price display, and a simple/printable invoice history. See
"How the open questions were resolved" at the top for each.

One cosmetic item left, not blocking: whether "sandbox" gets a visible
environment indicator anywhere in the UI/logs (e.g.
`settings.xendit_environment` used only for a banner/log line, never for
URL selection — Xendit's own API needs no such switch). Default is to
skip it entirely unless asked for.

## Explicitly out of scope for this integration

Per the confirmations above, this plan never builds: a Xendit refund
call, any mid-cycle cancellation/proration logic, auto-renewal/recurring
charges, PDF generation, or emailed receipts. If any of these become
real requirements later, they're new scope, not an extension of this
plan's phases.

## Implementation notes (what actually landed)

- **Models**: `app/models/payment.py::SubscriptionPayment` — exactly the
  Phase 1 shape above. Migration `alembic/versions/d30cd7e45698_subscription_payments.py`
  (autogenerated cleanly, additive only).
- **`app/services/xendit_client.py`** — `create_invoice`/`get_invoice`,
  matching the reference's request/response shape. `httpx` added to
  `requirements.txt` (the one new dependency, as the reference's own
  README flagged) and the backend image rebuilt to pick it up.
- **`app/config.py`** — `xendit_secret_key`, `xendit_webhook_token`,
  `xendit_success_redirect_url`, `xendit_failure_redirect_url`, and the
  approved cosmetic `xendit_environment` (default `"sandbox"`, informational
  only — never used to pick a URL, per Objective 2). `.env`/`.env.example`
  updated; `.env`'s `XENDIT_SECRET_KEY` is still blank (see Status above).
- **`content.py::PREMIUM_PRICING`** — the confirmed RM19.90/RM191.04 pair.
- **`app/services/subscription_payment.py`** — `checkout` (user-row lock,
  pending-payment reuse, calls Xendit, persists the invoice),
  `handle_xendit_webhook` (token check that *refuses to process* when
  unconfigured rather than silently skipping, amount-mismatch guard,
  idempotent on an already-`COMPLETED` payment, the `_apply_premium`
  state transition keyed on `billing_cycle`), `sync_payment`.
- **`app/api/v1/endpoints/subscription.py`** rewritten: `POST /checkout`,
  `GET /payments` (Phase 4.5), `POST /webhook/xendit`, `POST
  /sync-xendit/{payment_id}` added; `POST /subscribe` removed per
  resolution 3. **`/cancel`, `/reactivate`, `/start-trial` were kept,
  not removed** — "no cancellations, no refunds" was scoped in this doc
  to mean this integration never adds Xendit refund logic to them, not
  that the existing (payment-independent, pre-existing) cancel/reactivate
  toggle gets deleted; a more destructive, unrequested change wasn't
  taken on an ambiguous read. Flagging this explicitly in case the intent
  was broader.
- **Frontend**: `lib/api/subscription.ts` (`checkoutSubscription`,
  `listSubscriptionPayments`, `subscribe` removed),
  `lib/api/types.ts` (`CheckoutResponse`, `SubscriptionPaymentOut`),
  `membership.tsx` (billing-cycle toggle showing the flat charged amount
  only, Subscribe redirects to `invoice_url`, "Demo checkout" copy
  removed, a billing-history list with a Print button using Tailwind's
  `print:hidden` to drop interactive controls from the printed output —
  no PDF service, the browser's own print-to-PDF is the mechanism),
  new `/membership/payment-success` and `/membership/payment-failed`
  pages (re-fetch real subscription state on load; never treat the
  redirect itself as proof of payment).

### Verification

**Fully verified live**, real HTTP requests against the running stack:
- Auth guard on `/checkout` (401 unauthenticated), billing-cycle
  validation (400 on an invalid cycle).
- `/checkout` reaches the **real** `https://api.xendit.co/v2/invoices`
  and gets Xendit's own `INVALID_API_KEY` response back — confirms the
  request shape, auth header construction, and error propagation
  (502 with Xendit's own error body) all work correctly up to Xendit's
  authentication boundary. This is as far as verification can go without
  a real test-mode secret key.
- **Webhook settlement, fully exercised** via a synthetic Xendit-shaped
  payload against a manually-seeded `PENDING` payment row (since a real
  invoice can't be completed without a live key): wrong token → 401;
  correct token + `PAID` + matching amount → subscription correctly
  flips to `PREMIUM`/`ACTIVE` with `renews_at` = paid time + 30 days
  (MONTHLY) and confirmed separately at +365 days (YEARLY); amount
  mismatch → 400, rejected before touching the subscription; webhook
  redelivery on an already-`COMPLETED` payment → idempotent no-op;
  `EXPIRED` → payment marked `FAILED`, subscription untouched.
- `GET /subscription/payments` — confirmed returns the user's own
  payment history, newest first, correct fields.
- `/cancel`, `/reactivate`, `/start-trial` — confirmed still working
  unchanged.
- Frontend: `tsc --noEmit` and `eslint` clean on every changed file;
  `/membership`, `/membership/payment-success`, `/membership/payment-failed`
  all compile and load (200, no build errors).

**Update — a real key was added, and it's a live key, not a test one.**
`.env`'s `XENDIT_SECRET_KEY` was set to an `xnd_production_...` key —
`XENDIT_ENVIRONMENT=sandbox` in the same file is cosmetic only (see
Objective 2) and does not make this a sandbox key; Xendit has no
separate test hostname to fall back on. Flagged to the user before doing
anything with it; the user explicitly chose to verify live rather than
swap in a test key.

**Verified against the real, live Xendit API** (one real, unpaid
invoice created — RM19.90/MONTHLY, `checkout.xendit.co/web/6ab6292de...`,
not completed/paid, expires automatically after 24h per
`XENDIT_INVOICE_DURATION_SECONDS`):
- `POST /checkout` → 201, a genuine Xendit invoice created and correctly
  persisted (`xendit_invoice_id`, `invoice_url`, `status=PENDING` all
  correct in the DB).
- **Duplicate-invoice protection confirmed against the real API**: a
  second `/checkout` call for the same user/cycle returned the *same*
  `payment_id`/`invoice_url` and did not create a second Xendit invoice
  (row count stayed at 1) — the pending-payment-reuse logic works, so
  repeated clicks don't spam real invoices.
- `POST /sync-xendit/{payment_id}` → 200, successfully fetched the real
  invoice's live status from Xendit (`GET /v2/invoices/{id}`) and passed
  it through the settlement handler correctly (no-op, since it's still
  unpaid).

**Still not exercised, deliberately**: actually paying the invoice and
receiving a real webhook delivery from Xendit — that requires a genuine
charge going through, which wasn't done here. Everything up to and
including Xendit accepting/serving the invoice, and Gio's own settlement
logic (already thoroughly verified with synthetic `PAID`/`EXPIRED`/
mismatch/redelivery payloads earlier in this log), is confirmed correct.
To close the very last gap: register
`http://<backend-host>/api/v1/subscription/webhook/xendit` as the
invoice callback URL in the Xendit dashboard with a callback token
matching `XENDIT_WEBHOOK_TOKEN`, then complete a real payment.
