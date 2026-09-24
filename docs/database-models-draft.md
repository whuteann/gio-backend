# Gio Backend — Database Model Draft (for review)

**Status:** Draft, nothing implemented yet. Companion to
[`api-endpoints-draft.md`](./api-endpoints-draft.md) — same review pass,
just the storage side instead of the API side.

**Source of truth used:** `gio-member-app/lib/types.ts`. Worth flagging: that
file opens with the comment *"Domain types mirroring the Phase 1 System
Outline (§12 Database Model Outline)"* — so there's apparently a real spec
this was designed against. I don't have that document, only the frontend's
TypeScript mirror of it, so treat this draft as "reverse-engineered from the
mirror," not "verified against the source." If the System Outline itself is
available, we should reconcile against it directly instead.

## Conventions (proposed, matching the sibling backends)

- **Primary keys**: UUID (`gen_random_uuid()` / `uuid.uuid4()`), matching the
  pattern already used in `braceletBackend`'s models.
- **Timestamps**: `TIMESTAMPTZ`, stored UTC.
- **Naming**: snake_case tables/columns, plural table names.
- **Ownership**: every per-user table has a `user_id UUID NOT NULL REFERENCES
  users(id) ON DELETE CASCADE` — deleting a user cleans up their data.
- Frontend fields typed as a fixed-shape object (e.g. `Record<DimensionKey,
  number>`) are flattened into 4 named columns where another table already
  does that (`InnerStateSnapshot` does this for the same 4 dimensions), for
  consistency and so they're directly queryable/aggregable (needed for the
  Progress Trend chart's per-day-per-pillar series).
- Frontend fields typed as an *array of sub-objects* (`questions[]`,
  `items[]`) become child tables with a FK back to the parent, not a JSON
  column — they have their own real fields (dimension, rank, price...) that
  benefit from being queryable rows, not blobs.

---

## 1. Auth / Users

### `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| email | TEXT UNIQUE NOT NULL | |
| password_hash | TEXT NOT NULL | bcrypt |
| display_name | TEXT NOT NULL | |
| gid | TEXT UNIQUE NOT NULL | member-facing ID, e.g. `GIO-XXXX-XXXX` |
| status | TEXT NOT NULL DEFAULT 'ACTIVE' | enum, only `ACTIVE` exists today |
| preferred_language | TEXT NOT NULL DEFAULT 'en' | `en` \| `zh` |
| timezone | TEXT NOT NULL | |
| birthdate | DATE, nullable | set once at onboarding; drives numerology + colour-breakdown; **outlives recalibration** |
| onboarding_completed_at | TIMESTAMPTZ, nullable | |
| core_personality_last_recalibrated_at | TIMESTAMPTZ, nullable | drives the 24h recalibration cooldown |
| last_login_at | TIMESTAMPTZ, nullable | |
| created_at | TIMESTAMPTZ NOT NULL | |

**Relationships:** parent of every table below via `user_id`.

## 2. Subscription

### `subscriptions`
1:1 with `users` (either a unique `user_id` here, or just `id = user_id`).

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID UNIQUE NOT NULL FK → users.id | |
| plan | TEXT NOT NULL | `FREE` \| `PREMIUM` |
| billing_cycle | TEXT, nullable | `MONTHLY` \| `ANNUAL` |
| status | TEXT NOT NULL | `ACTIVE` \| `PENDING` \| `PAYMENT_FAILED` \| `CANCELLED` \| `EXPIRED` |
| starts_at | TIMESTAMPTZ, nullable | |
| renews_at | TIMESTAMPTZ, nullable | |
| expires_at | TIMESTAMPTZ, nullable | |
| cancelled_at | TIMESTAMPTZ, nullable | |
| first_free_reading_consumed_at | TIMESTAMPTZ, nullable | the free/Premium gate for Inner Reading keys off this one field |

## 3. Core Personality

### `core_personalities`
Versioned per user — a new row on every recalibration, `is_current` moved
forward.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID NOT NULL FK → users.id | |
| version | INTEGER NOT NULL | 1, 2, 3... |
| archetype | TEXT NOT NULL | `steady_anchor` \| `bright_spark` \| `quiet_strategist` \| `open_horizon` — FK candidate, see `archetypes` catalog table below |
| icon | TEXT NOT NULL | emoji, seeded once at generation time |
| thinking | SMALLINT NOT NULL | 0-100 |
| emotional_sensitivity | SMALLINT NOT NULL | 0-100 |
| adaptability | SMALLINT NOT NULL | 0-100 |
| willpower | SMALLINT NOT NULL | 0-100 |
| overall_explanation | TEXT NOT NULL | |
| pillar_explanations | JSONB NOT NULL | `{thinking, emotionalSensitivity, adaptability, willpower}` — just display copy, not queried per-field, so JSONB over 4 columns |
| assessment_version | TEXT NOT NULL | |
| is_current | BOOLEAN NOT NULL DEFAULT false | exactly one `true` row per user (partial unique index) |
| generated_at | TIMESTAMPTZ NOT NULL | |
| recalibrated_at | TIMESTAMPTZ, nullable | null on the v1 (onboarding) row |

**Relationships:** `recommendation_profiles.core_personality_id` → this
table (the personality active when a recommendation was generated).

## 4. Check-Ins

### `check_in_sessions`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID NOT NULL FK → users.id | |
| source | TEXT NOT NULL | `WEB` \| `WHATSAPP` |
| status | TEXT NOT NULL | `STARTED` \| `IN_PROGRESS` \| `COMPLETED` \| `ABANDONED` |
| blueprint_version | TEXT NOT NULL | e.g. `checkin-v1` |
| private_note | TEXT, nullable | never fed to recommendation generation |
| summary | TEXT, nullable | |
| started_at | TIMESTAMPTZ NOT NULL | |
| completed_at | TIMESTAMPTZ, nullable | |

### `check_in_answers`
One row per question answered in a session.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| check_in_session_id | UUID NOT NULL FK → check_in_sessions.id | |
| dimension | TEXT NOT NULL | one of the 4 `DimensionKey`s |
| question_text | TEXT NOT NULL | the exact phrasing shown (variants are picked at ask-time) |
| answer_value | SMALLINT NOT NULL | 1-5 raw |
| normalized_value | SMALLINT NOT NULL | 0-100 |
| generation_source | TEXT NOT NULL | `AI` \| `STATIC_FALLBACK` |
| order_index | SMALLINT NOT NULL | |
| answered_at | TIMESTAMPTZ NOT NULL | |

## 5. Inner Readings

### `inner_readings`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID NOT NULL FK → users.id | |
| status | TEXT NOT NULL | same enum as check-ins |
| blueprint_version | TEXT NOT NULL | e.g. `reading-v1` |
| emotional_energy | SMALLINT, nullable | flattened `dimensionScores` (null until completed) |
| mental_clarity | SMALLINT, nullable | |
| inner_pressure | SMALLINT, nullable | |
| grounding | SMALLINT, nullable | |
| result_summary | TEXT, nullable | |
| narrative | TEXT, nullable | |
| insight | TEXT, nullable | |
| reflection_question | TEXT, nullable | |
| title | TEXT, nullable | |
| subtitle | TEXT, nullable | |
| started_at | TIMESTAMPTZ NOT NULL | |
| completed_at | TIMESTAMPTZ, nullable | |
| created_at | TIMESTAMPTZ NOT NULL | |

### `inner_reading_answers`
Same shape as `check_in_answers`, FK'd to `inner_readings.id` instead.
(Genuinely tempted to merge these two answer tables into one
`session_answers` table with a `session_type` + polymorphic parent — noted
as an open question below rather than picked unilaterally.)

## 6. Inner State Snapshots

### `inner_state_snapshots`
Created by *both* a check-in and an Inner Reading — the one table the
Progress Trend chart and "Your inner state" card both read from.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID NOT NULL FK → users.id | |
| source_type | TEXT NOT NULL | `CHECK_IN` \| `INNER_READING` |
| source_id | UUID NOT NULL | polymorphic — points at `check_in_sessions.id` or `inner_readings.id` depending on `source_type`. No single FK constraint possible; enforce via a trigger/check or just app-level integrity (see open question) |
| emotional_energy | SMALLINT NOT NULL | 0-100 |
| mental_clarity | SMALLINT NOT NULL | 0-100 |
| inner_pressure | SMALLINT NOT NULL | 0-100 |
| grounding | SMALLINT NOT NULL | 0-100 |
| balance | SMALLINT NOT NULL | derived: avg of the 4 (pressure inverted) |
| current_focus | TEXT NOT NULL | e.g. `"Releasing pressure"` |
| summary | TEXT NOT NULL | |
| created_at | TIMESTAMPTZ NOT NULL | index this — it's the column the trend chart queries a date range on |

## 7. Recommendations

### `recommendation_profiles`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID NOT NULL FK → users.id | |
| state_snapshot_id | UUID NOT NULL FK → inner_state_snapshots.id | |
| core_personality_id | UUID NOT NULL FK → core_personalities.id | |
| trigger_type | TEXT NOT NULL | `CHECK_IN` \| `INNER_READING` |
| trigger_source_id | UUID NOT NULL | same polymorphic caveat as snapshots' `source_id` |
| current_focus | TEXT NOT NULL | |
| summary | TEXT NOT NULL | |
| primary_colour | TEXT NOT NULL | hex or CSS var string — could instead be `colour_key TEXT FK → colours.key`, see catalog section |
| status | TEXT NOT NULL | `GENERATING` \| `READY` \| `FAILED` |
| generated_at | TIMESTAMPTZ NOT NULL | this is what "Your colour history" queries and sorts by |

### `recommendation_items`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| recommendation_profile_id | UUID NOT NULL FK → recommendation_profiles.id | |
| type | TEXT NOT NULL | `COLOUR` \| `ROUTINE` \| `SCENT` \| `WEARABLE` \| `PRODUCT` |
| reference_id | TEXT, nullable | e.g. a `products.id` when `type = PRODUCT` |
| title | TEXT NOT NULL | |
| reason | TEXT NOT NULL | |
| rank | SMALLINT NOT NULL | display order |
| image_url | TEXT, nullable | |
| price | NUMERIC(10,2), nullable | |
| destination_url | TEXT, nullable | |

## 8. Gamification

### `xp_transactions`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID NOT NULL FK → users.id | |
| amount | INTEGER NOT NULL | |
| source_action | TEXT NOT NULL | `CHECK_IN` \| `INNER_READING` \| `DAILY_QUEST_BONUS` \| `STREAK_MILESTONE` |
| source_key | TEXT NOT NULL | dedupe key, e.g. `CHECK_IN:2026-09-06` |
| created_at | TIMESTAMPTZ NOT NULL | |

`UNIQUE (user_id, source_key)` — this is exactly what stops a user being
double-awarded XP for the same day/action; enforce it as a DB constraint, not
just app logic.

### `user_quests`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID NOT NULL FK → users.id | |
| quest | TEXT NOT NULL | `LOGIN` \| `CHECK_IN` \| `INNER_READING` |
| date | DATE NOT NULL | local date |
| completed_at | TIMESTAMPTZ NOT NULL | |

`UNIQUE (user_id, quest, date)`.

### `user_streaks`
1:1 with `users` — a single row updated in place, not a history.

| Column | Type | Notes |
|---|---|---|
| user_id | UUID PK, FK → users.id | |
| current | INTEGER NOT NULL DEFAULT 0 | |
| best | INTEGER NOT NULL DEFAULT 0 | |
| last_reflection_date | DATE, nullable | |
| milestones_awarded | INTEGER[] NOT NULL DEFAULT '{}' | e.g. `{7,30}` — or a child table `user_streak_milestones(user_id, days)` if we'd rather avoid a Postgres array column |

### `garden_progress`
1:1 with `users`, also updated in place — **no history is kept today**
(worth flagging: if "garden over time" is ever wanted, this needs to become
a real per-week table instead).

| Column | Type | Notes |
|---|---|---|
| user_id | UUID PK, FK → users.id | |
| week_start | DATE NOT NULL | Monday of the current tracked week |
| stage | SMALLINT NOT NULL DEFAULT 0 | 0-4 |
| actions_this_week | INTEGER NOT NULL DEFAULT 0 | |

### `user_badges`
| Column | Type | Notes |
|---|---|---|
| user_id | UUID NOT NULL FK → users.id | |
| badge_key | TEXT NOT NULL FK → badge_definitions.key | |
| earned_at | TIMESTAMPTZ NOT NULL | |

`PRIMARY KEY (user_id, badge_key)`.

### `user_rewards`
| Column | Type | Notes |
|---|---|---|
| user_id | UUID NOT NULL FK → users.id | |
| reward_key | TEXT NOT NULL FK → reward_definitions.key | |
| state | TEXT NOT NULL | `LOCKED` \| `UNLOCKED` \| `REDEEMED` |
| unlocked_at | TIMESTAMPTZ, nullable | |
| redeemed_at | TIMESTAMPTZ, nullable | |

`PRIMARY KEY (user_id, reward_key)`.

## 9. Journal

### `journal_entries`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID NOT NULL FK → users.id | |
| content | TEXT NOT NULL | markdown, free text |
| mood | TEXT NOT NULL | server-tagged on write |
| theme | TEXT NOT NULL | server-tagged on write |
| created_at | TIMESTAMPTZ NOT NULL | index this — insights/history both query by date |

---

## Catalog / reference content

None of this is per-user data — it's the same for every account. Two ways to
handle it, and I'd lean toward a mix rather than one answer for everything:

**Worth being real tables** (other rows reference them by key/FK, or the
product catalog plausibly changes without a deploy):

| Table | Columns (sketch) |
|---|---|
| `products` | id, title, colour_tag, element_tags TEXT[], price, image_seed, available |
| `badge_definitions` | key PK, group, title, description, icon |
| `reward_definitions` | key PK, title, description, icon, requirement (text); **eligibility is a small rule** (`xp >= N` / `streak_best >= N` / `badges.length >= N`) — that logic stays in application code, not a column, since it's a predicate, not a value |
| `colours` | key PK (`scarlet`/`russet`/`gold`/`forest`/`ocean`), name, swatch, traits TEXT[3], description, article, benefit, affirmations TEXT[2], positive_traits TEXT[5], negative_traits TEXT[5] |
| `archetypes` | key PK, name, tagline, traits TEXT[3], reminder, icons TEXT[], circle_class_name, colour_reason, overall, pillars JSONB |

**Probably *not* worth tables** — these are just "pick one variant
deterministically by a seeded hash" phrasing pools (`INSIGHT_LIBRARY`,
`HEADLINE_LIBRARY`, `CHECKIN_QUESTION_POOL`, `READING_QUESTION_POOL`,
`FOCUS_COLOUR_REASON`, `JOURNAL_MOODS`, `JOURNAL_THEMES`,
`BASELINE_ASSESSMENT`). Nothing ever filters, joins, or aggregates on them —
they're read wholesale and hashed into. Recommend keeping these as backend
application constants (a direct Python port of `lib/blueprints.ts`, same as
today), still served through the `/catalog/*` / `/personality/baseline-
questions` endpoints — just from a Python dict, not a `SELECT`. Revisit only
if we want them admin-editable without a redeploy.

---

## Open questions for review

1. **Polymorphic `source_id` / `trigger_source_id`** (on
   `inner_state_snapshots` and `recommendation_profiles`): no clean single FK
   since the parent can be either table. Options: (a) leave as a bare UUID +
   app-level integrity, (b) two nullable FK columns
   (`check_in_session_id`, `inner_reading_id`) with a check constraint that
   exactly one is set, (c) a `CHECK (source_type IN (...))` plus a DB
   trigger. Leaning (b) — plays nicer with real FK constraints — but that's
   a genuine tradeoff to pick together.
2. **Merge `check_in_answers` / `inner_reading_answers`** into one
   `session_answers` table (same shape, same polymorphic-parent problem as
   #1), or keep them separate and simple? Separate is simpler now; merged
   avoids near-duplicate schema if a third session type ever shows up.
3. **`primary_colour` on `recommendation_profiles`**: store the resolved hex
   string (as today), or a `colour_key FK → colours.key` and resolve the
   swatch at read time? FK is more normalized; hex is what the frontend
   already expects verbatim.
4. **`garden_progress` has no history** — confirm that's actually fine (only
   "this week's" stage has ever mattered), or should it become a per-week
   table now, before there's data to migrate?
5. Same "server table vs. app constant" call as raised in the endpoints doc
   — do we agree with the catalog split above, or want everything in real
   tables from day one?
