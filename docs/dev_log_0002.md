# dev_log_0002 — Authenticated password change

**Status:** Implemented and verified end-to-end (curl + live browser).

## What this is (and isn't)

`PATCH /api/v1/me/password` — a logged-in user changes their own password.
This is **not** the "forgot password" flow flagged as a deliberate gap in
`dev_log_0001.md` (that one needs to work for someone who *can't* log in, so
it needs email + a verification token). This one only needs the caller's
existing JWT as proof of identity, so it's a single field —
`{"new_password": "..."}` — no current-password re-entry, no token.

- `app/schemas/user.py`: `ChangePasswordRequest`, `new_password` with
  `min_length=6` (matches the frontend register form's existing rule).
- `app/api/v1/endpoints/me.py`: `PATCH /me/password`, hashes with the same
  `hash_password()` used at registration, `204 No Content` on success.

## Verified

Via curl: registered a user, changed the password, confirmed the *old*
password now `401`s on login and the *new* one succeeds, confirmed a
too-short password `422`s with a clear message. Then again through the real
UI (see `gio-member-app/docs/dev_log_0002.md`) — same result, full round
trip through the browser.
