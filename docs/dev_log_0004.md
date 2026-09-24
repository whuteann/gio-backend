# dev_log_0004 — Access/refresh token flow

**Status:** Implemented and verified end-to-end (curl + live browser via
`gio-member-app`, including a real expired-token repro). Companion to
`gio-member-app/docs/dev_log_0004.md`.

## What this fixes

Clicking "Start free trial" on `/membership` crashed the page with Next.js's
runtime error overlay: `ApiError: Invalid or expired token`. The backend
only ever issued a single JWT access token
(`ACCESS_TOKEN_EXPIRE_MINUTES=30`, no refresh mechanism at all), and nothing
on the frontend caught a 401 specially — 30 minutes after logging in, the
next API call from any page just crashed instead of failing gracefully.

## What was added

- `app/core/security.py`: `create_refresh_token`/`decode_refresh_token`,
  alongside the existing `create_access_token`/`decode_access_token`. Both
  token kinds now carry a `"type": "access"` / `"type": "refresh"` claim so
  one can't be used in place of the other — `decode_access_token` rejects a
  refresh token and vice versa.
- `app/config.py`: `refresh_token_expire_days: int = 30`.
- `app/schemas/auth.py`: `TokenResponse` gained `refresh_token`; new
  `RefreshRequest`.
- `app/api/v1/endpoints/auth.py`: `register`/`login` both return a
  `refresh_token` alongside the access token now. New `POST /auth/refresh`
  — decodes the refresh token, 401s if invalid/expired/wrong-type or the
  user no longer exists, otherwise **rotates**: returns a brand-new
  access+refresh pair.

Kept **stateless** — no new `refresh_tokens` table, no revocation list.
Consistent with this backend's existing all-JWT auth, but worth stating the
trade-off explicitly: an individual refresh token can't be revoked early
(no "sign out this one device"); only its expiry or rotating `SECRET_KEY`
invalidates it. Fine for a demo app.

One side effect worth knowing: adding the `type` claim means tokens issued
before this change no longer decode (`payload.get("type")` is `None`, not
`"access"`) — anyone with an old session gets logged out once. Expected,
not a bug.

## What was tested

Curl: registered → confirmed `refresh_token` present; `POST /auth/refresh`
with it → fresh pair; the same call with an *access* token in place of a
refresh token → 401 (type-claim check working); garbage string → 401;
confirmed two refreshes a couple seconds apart actually produce different
tokens (rotation working, not just JWT-encoding determinism within the same
second).

Then a full live Playwright pass through `gio-member-app` with
`ACCESS_TOKEN_EXPIRE_MINUTES` temporarily dropped to 1: registered, waited
past expiry, clicked "Start free trial" (the exact original repro) —
succeeded with no error overlay, Redux's access token visibly changed
(proving a refresh actually happened, not luck), and the trial banner
appeared (proving the *retried* request succeeded, not just the refresh
call itself). Separately corrupted both tokens client-side and repeated —
confirmed a clean redirect to `/auth/login` with no uncaught error, instead
of the original crash. See the frontend's dev log for the one real bug this
surfaced (a still-uncaught rejection *after* the redirect) and its fix.
