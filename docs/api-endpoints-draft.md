# Gio Backend — API Endpoint Draft (for review)

**Status:** Draft, nothing implemented yet. This is a proposed 1:1 mapping of
what `gio-member-app` currently fakes client-side (in `AppStateContext.tsx`,
localStorage) onto real REST endpoints, so we have something concrete to
review and adjust before writing any FastAPI code.

Source of truth used to build this: `gio-member-app/lib/types.ts`,
`context/AppStateContext.tsx`, `lib/entitlement.ts`, `lib/blueprints.ts`, and
every page under `gio-member-app/pages/`.

## Conventions (proposed)

- Base path: `/api/v1`
- Auth: `Authorization: Bearer <JWT>`, issued by login/register. Every
  authenticated endpoint scopes to the caller (from the token) — no `user_id`
  in the path anywhere.
- Errors: standard HTTP status codes (`401` no/bad token, `403` plan-gated,
  `404` not found, `429` rate-limited) with a JSON body `{"detail": "..."}`.
- List endpoints are paginated (`?limit=&cursor=` or `?page=` — TBD) and
  **plan-gated server-side** (see "History limits" below) rather than the
  frontend just slicing an array it already has, like today.
- "Maps to" column below points at the current frontend function or page so
  this is easy to cross-check against what already exists.

---

## 1. Auth

| Method | Path | Description | Maps to |
|---|---|---|---|
| POST | `/auth/register` | `{email, password, displayName, language}` → creates account, returns `{access_token, user}` | `register()` |
| POST | `/auth/login` | `{email, password}` → `{access_token, user}` | `login()` |
| POST | `/auth/logout` | Invalidate/blacklist token (or client-side-only if we skip a blacklist for now) | `logout()` |
| POST | `/auth/forgot-password` | `{email}` → sends a reset link/code (real email delivery — see note) | `pages/auth/forgot-password.tsx` |
| POST | `/auth/reset-password` | `{token, newPassword}` → resets password | `resetPassword()` |

**⚠️ Security note:** the current frontend's `resetPassword({email, newPassword})`
resets a password directly from an email address alone, with no verification
step — that's a mock shortcut with nowhere to send a real email. The real
backend should **not** port this as-is: it needs an actual token-based flow
(`forgot-password` issues a short-lived token/emails a link, `reset-password`
consumes that token). Flagging this as a deliberate deviation, not an
oversight.

**Excluded on purpose:** `loginDemo()` (the "Continue as Demo Member" button)
is a frontend/demo-data convenience, not something the real backend needs to
support.

## 2. Current user / profile

| Method | Path | Description | Maps to |
|---|---|---|---|
| GET | `/me` | Current user + subscription summary | `data.user`, `data.subscription` (read everywhere, e.g. `AppShell`) |
| PATCH | `/me` | Update `{displayName, preferredLanguage, timezone}` | `updateProfile()`, `pages/profile.tsx` |

## 3. Onboarding & Core Personality

The personality model changed recently: **initial onboarding is now
birthdate-derived** (a deterministic "numerology reading" simulation), while
**recalibration still uses the original A/B baseline quiz**. These are two
genuinely different inputs, not the same flow twice.

| Method | Path | Description | Maps to |
|---|---|---|---|
| POST | `/personality/onboarding` | `{birthdate}` → stores `user.birthdate`, deterministically derives archetype + pillar scores + supportive colour seed, creates CorePersonality v1 | `completeOnboardingBirthdate()` |
| POST | `/onboarding/complete` | Marks `onboardingCompletedAt` | `markOnboardingComplete()` |
| GET | `/personality/current` | Current CorePersonality (archetype, pillars, icon, overview text) | `useCurrentPersonality()` |
| GET | `/personality/baseline-questions` | The A/B recalibration quiz question bank | `BASELINE_ASSESSMENT` (`getBaselineQuestions()`) |
| POST | `/personality/recalibrate` | `{answers}` → new versioned CorePersonality. Rate-limited to once/24h server-side → `429` with `{nextEligibleAt}` if too soon | `recalibratePersonality()`, `cooldownRemainingMs()` |
| GET | `/personality/numerology` | Life path / birthday / talent numbers + trait copy, derived from `user.birthdate` | `NumerologySection`, `lifePathNumber()` etc. |
| GET | `/personality/colour-breakdown` | Per-colour affinity scores derived from `user.birthdate` | `ColourBreakdown`, `colourAffinityScores()` |

**Design note:** numerology and colour-breakdown are *pure functions* of
`birthdate` — no extra stored state. They could stay purely client-side
(frontend already has `birthdate` after `/me`) instead of being served by two
extra endpoints. Recommend serving them from the backend anyway so the
"reading" logic has one source of truth and can change without a frontend
redeploy — but this is a real either/or worth deciding, not settled by me.

## 4. Check-Ins

| Method | Path | Description | Maps to |
|---|---|---|---|
| GET | `/check-ins/questions` | Today's check-in question set (blueprint-versioned) | `buildQuestionOrder(CHECKIN_QUESTION_POOL, ...)` |
| POST | `/check-ins` | Submit answers `+` optional private note → creates session, triggers the side-effect cascade (see below) | `submitCheckIn()` |
| GET | `/check-ins` | History, paginated, **limited to last 3 on Free** | `pages/check-in/history.tsx`, `historyLimit()` |
| GET | `/check-ins/{id}` | Single session detail | — |

## 5. Inner Readings

| Method | Path | Description | Maps to |
|---|---|---|---|
| GET | `/inner-readings/questions` | Reading question set | `buildQuestionOrder(READING_QUESTION_POOL, ...)` |
| POST | `/inner-readings` | Submit answers → creates reading (title/subtitle/insight/reflection question generated server-side) + triggers cascade. **Gated**: first one free, then Premium-only → `403` with a gate reason if blocked | `submitInnerReading()`, `innerReadingGate()` |
| GET | `/inner-readings` | History, paginated, **limited to last 3 on Free** | `pages/inner-reading/history.tsx` |
| GET | `/inner-readings/{id}` | Full reading (narrative, insight, dimension scores) | `pages/inner-reading/[id]/result.tsx` |

## 6. Inner State & Progress Trend

| Method | Path | Description | Maps to |
|---|---|---|---|
| GET | `/state-snapshots/latest` | Most recent snapshot (dashboard "Your inner state") | `data.stateSnapshots[last]` |
| GET | `/state-snapshots/trend?period=weekly\|monthly` | One value per day per pillar, forward-filled. **`monthly` is Premium-only** — `weekly` on Free | `lib/trend.ts`, dashboard "Progress Trend" card |

## 7. Recommendations & Colour Psychology

| Method | Path | Description | Maps to |
|---|---|---|---|
| GET | `/recommendations/latest` | Latest recommendation profile (colour, routine, matched products) | `pages/recommendation.tsx` |
| GET | `/recommendations` | History (backs "Your colour history") | `pages/colour-psychology/index.tsx` |
| GET | `/colours` | Static catalog: Scarlet/Russet/Gold/Forest/Ocean, traits + description | `COLOUR_LIBRARY` |
| GET | `/colours/{key}` | Single colour's full article (used by the detail page) | `pages/colour-psychology/[key].tsx` |

## 8. Progress / Gamification

| Method | Path | Description | Maps to |
|---|---|---|---|
| GET | `/progress` | Bundle: XP total, streak, garden stage, today's quest completion, earned badges | `pages/progress.tsx`, dashboard "Progress" card |

(Proposed as one bundled endpoint since every current consumer reads all of
it together. Happy to split into `/xp`, `/streak`, `/garden`, `/quests/today`,
`/badges` if that's preferred — flagging as an open question below.)

**Open question — "login" quest:** today, `AppStateContext` silently marks
the `LOGIN` quest done on every app load via a `useEffect`. There's no clean
REST equivalent of "just visiting counts" — options: (a) any authenticated
request on a new calendar day implicitly completes it server-side, (b) an
explicit `POST /progress/login-ping` the frontend calls once per session.
Needs a decision.

## 9. Rewards

| Method | Path | Description | Maps to |
|---|---|---|---|
| GET | `/rewards` | Reward definitions + this user's unlock/redeemed state | `pages/rewards.tsx` |
| POST | `/rewards/{key}/redeem` | Redeem an unlocked reward | `redeemReward()` |

## 10. Journal

| Method | Path | Description | Maps to |
|---|---|---|---|
| GET | `/journal/entries` | List entries, paginated | `pages/journal.tsx` |
| POST | `/journal/entries` | `{content}` → creates entry, server tags mood/theme | `addJournalEntry()` |
| GET | `/journal/insights` | `{entriesThisWeek, entriesDelta, topMood, topTheme}` | `buildJournalInsights()` |

No edit/delete exists in the frontend today — flagging as a gap to decide on,
not assuming it's intentionally excluded forever.

## 11. Subscription / Membership

| Method | Path | Description | Maps to |
|---|---|---|---|
| GET | `/subscription` | Current plan/status/renewal dates | `data.subscription` |
| POST | `/subscription/subscribe` | `{billingCycle}` → activates Premium | `subscribe()` |
| POST | `/subscription/cancel` | Cancels (stays active until period end) | `cancelSubscription()` |
| POST | `/subscription/reactivate` | Un-cancels before period end | `reactivateSubscription()` |

**⚠️ Note:** the frontend's `subscribe()` just flips the plan to PREMIUM
instantly — there's no real payment step anywhere in this app. Real billing
(Stripe or otherwise) is out of scope for this draft; these three endpoints
as listed only make sense if we're intentionally staying mock/manual for now.

## 12. Catalog (static reference content)

Content that's currently hardcoded client-side in `lib/blueprints.ts`. Same
either/or as numerology above: none of it is per-user data, so it *could*
stay a frontend constant. Listed here in case we'd rather the backend own it
(e.g. so blueprint versions like `checkin-v1` / `reading-v1` can change
without a frontend redeploy, which the data model's `blueprintVersion` fields
already imply was the intent).

| Method | Path | Description |
|---|---|---|
| GET | `/catalog/products` | Product list used by recommendations & shop links |
| GET | `/catalog/badges` | Badge definitions |
| GET | `/catalog/archetypes` | Archetype copy (name, traits, overview, reminder) |

## Explicitly out of scope

- **Commerce** (`/shop/[id]`, cart, checkout): the frontend already treats
  this as a stub pointing at an *existing, external* Gio store — this backend
  doesn't own products/cart/checkout, per the comment in `shop/[id].tsx`.
- **Real payments/billing** — see note under Membership.
- **Real transactional email** — see note under Auth.

## Cross-cutting design note: side-effect cascades

`POST /check-ins` and `POST /inner-readings` aren't plain creates — in the
current mock, one submission triggers a whole cascade: new
`InnerStateSnapshot` → XP award → streak update → garden update → badge
evaluation → reward evaluation → new recommendation (colour + products). In
the real backend this whole chain needs to happen **server-side, in one DB
transaction**, and each endpoint's response should probably return the same
`{sessionId/readingId, outcome: {xpAwarded, bonusAwarded, milestone,
newBadges}}` shape the frontend already expects, so the frontend barely has
to change.

## Open questions for review

1. Split `/progress` into per-resource endpoints, or keep it bundled?
2. Numerology / colour-breakdown / catalog content: served by the backend, or
   stay as frontend constants? (Three call this out above.)
3. "Login quest" — implicit-on-request vs. an explicit ping endpoint?
4. Pagination style for history endpoints — cursor or page number?
5. Journal edit/delete — add now, or genuinely out of scope?
6. Any of this map to an existing "System Outline" doc I should be
   reconciling against instead of the frontend code?
