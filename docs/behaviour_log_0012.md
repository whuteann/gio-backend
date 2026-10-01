# behaviour_log_0012 — Product recommendation: a narrative prompt, one unified colour, and the real product-filter API

**Status:** Implemented and verified live (all 6 deliverables). See
"Implementation notes" at the bottom.

## Confirming what I understood

1. **A "narrative prompt"** — a mad-libs-style templated block of text,
   assembled from code (not written by the AI), that becomes the shared
   grounding context for the product-recommendation AI step. Its
   ingredients: the (now-unified) recommended colour, the latest Inner
   State snapshot, the last 5 `NarrativeEntry` summaries, and journal
   entries. This is the same "computed facts first, AI narrates/selects
   around them" principle every other AI call in this app already follows
   (`app/services/ai_outcome.py`) — just applied to a new consumer.
2. **Journals currently carry no narrative weight** — `NarrativeEntry` only
   exists for check-ins and Inner Readings today. You're asking that
   journal entries also produce a `NarrativeEntry`, so the last-5 memory
   feed (and therefore the narrative prompt) reflects journaling too, not
   just check-ins/readings.
3. **The third-party product-filter API** (`third-party-product-filter-api/`)
   replaces today's 7-item hardcoded stub. Its `elements` query parameter
   is a product-element name — and it happens to exactly match our 5
   colour keys (`scarlet`, `russet`, `gold`, `forest`, `ocean` —
   `app/services/content.py::COLOURS`). So: filter the live catalog by
   the unified recommended colour, hand the AI the resulting candidate
   list (id + name + price, not full descriptions — keeps the prompt
   small), and have it return which candidate ids to actually recommend.
   The AI **must** be used here — this is the "AI selects from a
   constrained candidate list" pattern (already used for
   affirmation/insight/reflection-question ids in `behaviour_log_0011.md`),
   not free-form generation and not pure rule-based filtering either.
4. **Frontend display + navigation**: whatever ids the AI returns get
   rendered as product cards, and clicking one navigates to
   `https://www.giobyquartzic.com/products/{id}` — the live storefront,
   using the same `id` the filter API returned.
5. **"Colour recommended needs to be unified — there must always be one
   consistent one for product recommendation purposes."** This is a real
   gap I can already see in the code (below), not just a phrasing
   concern — flagging the specific fix I'm proposing for confirmation.

## Current state — what's already built vs. what's a stub

**The colour-consistency problem is real.** There are two independent
"colour" concepts live in the app right now:

- `RecommendationProfile.colour_key` / `InnerStateSnapshot.colour_key` — a
  **dynamic** colour, recomputed on every check-in/Inner Reading from
  `FOCUS_TO_COLOUR[focus_label]` (`app/services/recommendation.py`). This
  is what the dashboard's "Colour of the Day" card shows, and it changes
  as the user's focus changes.
- Core Personality's `topColourKey(personality)` — a **static** colour
  representing the user's inherent type (from onboarding's Colour
  Breakdown scores), shown on the Core Personality page and its Growth
  Tree.

Both are legitimate, but they answer different questions ("what does this
person need right now" vs. "who is this person"), and nothing today
declares which one is authoritative for *product matching*. My proposed
resolution (Phase 1 below) is to make that explicit rather than leave it
implicit.

**Narrative memory only covers two of three reflection surfaces.**
`app/services/narrative.py` / `app/models/narrative.py`: `NarrativeEntry`
has a check constraint requiring exactly one of `check_in_session_id` /
`inner_reading_id` — there's no column for a journal entry, and
`app/api/v1/endpoints/journal.py::create_entry` never calls
`create_narrative_entry`. `recent_narrative_summaries()` already defaults
to the last 5 (`RECENT_ENTRY_LIMIT = 5`), matching what you described.
Journal's own tagging (`app/services/journal.py::tag_journal_entry`) is
deterministic (hashed mood/theme pick, no AI, no narrative write) — it's
completely outside the memory/recommendation loop today.

**Product recommendation is a hardcoded stub end to end.**
`app/services/recommendation.py::_fetch_products_stub()` returns 7
fictional products; `build_recommendation()` matches them by simple tag
intersection (`set(product.tags) & set(profile_data.tags)`) — no HTTP
call, no AI call, nothing external. This runs on *every* check-in and
Inner Reading submission (called from `cascade.py::apply_reflection_side_effects`),
which matters for Phase 4's latency/cost discussion below.

**The frontend is already fully wired for real data — nothing to build
there.** `RecommendationItem.destination_url` and `reference_id` columns
already exist and already flow through the API schema
(`app/schemas/recommendation.py`) to `gio-member-app/lib/api/types.ts` to
`components/ui/ProductCard.tsx`, which already renders `item.imageUrl`,
`item.price`, `item.reason`, and links out via `item.destinationUrl` —
today it's just always `null` because the stub never sets it. This is a
backend content-quality upgrade, not a frontend build.

One display bug I noticed while auditing this, unrelated to your ask but
worth flagging: `ProductCard.tsx` hardcodes a `$` prefix on price
(`${item.price}`), but the filter API's default/only-tested currency is
`MYR`. Once real prices flow through, `$446` will read as USD when it's
actually MYR. Separate fix, not blocking this plan — noting it so it
doesn't get lost.

## The third-party API, as read for this purpose

`GET https://api.giobyquartzic.com/api/v1/products/filter` — plain HTTPS,
no auth, JSON in/out (`third-party-product-filter-api/README.md`).
Relevant parameters:

- `elements` (repeated) — exact match, and this is the one that matters
  most here: **it takes our colour keys directly** (`elements=scarlet`).
  Repeat the key for multiple colours (`elements=scarlet&elements=ocean`)
  — not needed here since Phase 1 unifies to a single colour per request.
- `is_active=true` — exclude inactive products (the API's `in_stock` field
  is *not* reliable for this — it's just a mirror of `is_active`).
- `per_page` (1–100, default 10), `page`, `has_next` — standard paging.
  I'm proposing a single page, `per_page=20`, as the AI's candidate pool
  (Phase 4) — enough variety without a multi-page walk on every
  submission.
- `currency=MYR` (default) — matches the currency the catalog is actually
  priced in; no conversion needed unless we want a different display
  currency later.
- Response `data[]` items: `id` (UUID — this is the id used in the
  storefront URL), `sku`, `name`, `type`, `price` (decimal **string**,
  needs `Decimal()` parsing before it goes into
  `RecommendationItem.price: Numeric(10,2)`), `currency`, `color`,
  `description`, `primary_image`, `is_active`, `is_featured`,
  `stone_types`. `color`/`description`/`primary_category` can be `null`.

## Proposed architecture

### Phase 1 — Unify the recommended colour

Declare `RecommendationProfile.colour_key` (equivalently, the latest
`InnerStateSnapshot.colour_key`) as the **single canonical "recommended
colour"** for anything product-related: the narrative prompt (Phase 3),
the filter API's `elements` param (Phase 4), and anywhere else a "what
colour is this recommendation" question comes up. It's already
deterministic (`FOCUS_TO_COLOUR`), already computed once per
check-in/reading, and already stored — this phase is a *naming/contract*
change, not a new computation. Core Personality's `topColourKey` stays
exactly as it is, untouched, answering a different question ("who are
you") that this plan doesn't touch. **Flagging for explicit confirmation**
since "unify" could also have meant something else (e.g. making the two
concepts converge into one value) — my reading is that they should stay
two different concepts, with product recommendation clearly pinned to
one of them.

### Phase 2 — Extend Narrative to cover journals

- `app/models/narrative.py`: add `journal_entry_id` (nullable FK to
  `journal_entries.id`, `ondelete="CASCADE"`) to `NarrativeEntry`, and
  widen `ck_narrative_entry_single_source` to require exactly one of the
  three source columns instead of two. Migration: additive column + a
  constraint replacement, same shape as the original narrative migration.
- `app/services/narrative.py::create_narrative_entry`: add
  `journal_entry_id` as a third optional parameter alongside the existing
  two, `source_type="JOURNAL"`.
- `app/api/v1/endpoints/journal.py::create_entry`: after saving the
  `JournalEntry`, call `create_narrative_entry(..., source_type="JOURNAL", journal_entry_id=entry.id, summary=...)`.
  **Open question**: what generates `summary` here? Two options —
  (a) **deterministic**, e.g. `f"Journaled about {theme.lower()} ({mood.lower()})."`,
  consistent with journal's own tagging already being non-AI and adding
  zero latency/cost to saving a journal entry; or (b) a genuine AI-written
  ~20-word summary (matching check-in/reading's `narrative_summary`
  voice), which means `create_entry` becomes `async def` and takes on an
  OpenAI round-trip it doesn't have today. My default recommendation is
  (a) — journaling should stay instant to save, and the summary only
  needs to be *useful as memory*, not eloquent — but this is your call to
  make explicitly rather than one I make silently, since it changes the
  journal save endpoint's latency profile either way.

### Phase 3 — The narrative prompt assembler (the "mad libs")

New function, e.g. `app/services/narrative_prompt.py::build_narrative_prompt(db, user) -> str`,
gathering:

1. The unified recommended colour (Phase 1) + its name/traits from
   `content.py::COLOURS`.
2. The latest `InnerStateSnapshot`'s four dims + resolved focus label.
3. The last 5 `NarrativeEntry` summaries (Phase 2 makes this span
   check-ins, readings, *and* journals) — reusing
   `narrative.py::recent_narrative_summaries()` as-is, since it already
   queries generically by `narrative_profile_id`, not by source type.
4. A rollup of recent journaling from the existing
   `journal.py::build_journal_insights()` (entries this week, top
   mood/theme) — this is a second, complementary signal to the raw
   narrative summaries (frequency/mood *pattern*, not individual entries).

Assembled into one template block, following the exact style already
established in `ai_outcome.py` (plain stated facts + a bulleted memory
block), e.g.:

```
This user's current focus is "{focus_label}". Their supportive colour
right now is {colour_name} ({colour_traits}).

Inner state: Emotional Energy {ee}/100, Mental Clarity {mc}/100, Inner
Pressure {ip}/100, Grounding {g}/100.

Recent reflections, oldest to newest:
- {summary 1}
- {summary 2}
...

Recent journaling: {entries_this_week} entries this week
({entries_delta:+d} vs. last week), most common mood "{top_mood}",
most common theme "{top_theme}".
```

This string becomes a single reusable building block — Phase 4 is its
first consumer, but nothing about it is product-recommendation-specific,
so it's written as its own module rather than inlined into
`recommendation.py`.

### Phase 4 — Real product fetch + AI selection, replacing the stub

- New `app/services/product_api.py`: an async HTTP client (matching the
  `AsyncOpenAI` pattern already used for the AI client) wrapping
  `GET /api/v1/products/filter?elements={colour}&is_active=true&per_page=20`.
  Returns the parsed `data[]` list (id, name, price as `Decimal`,
  currency, primary_image). Best-effort: on a non-2xx response, a
  timeout, or an empty `data[]`, this returns `[]` rather than raising —
  a failed/slow third-party call should degrade to "no product
  recommendations this time," not break check-in/reading submission
  entirely (submission's snapshot/XP/streak/badges must never depend on
  an external vendor's uptime).
- New AI step (naturally sits in `ai_outcome.py` alongside the existing
  generation calls, or a new `ai_recommendation.py` if that file is
  getting large): given the narrative prompt (Phase 3) + a compact
  candidate list (`id: "name" — RM{price}`, capped to the ~20 fetched),
  the AI picks an ordered list of product ids to recommend, each with a
  short `reason`. Same "constrained selection" mechanism as
  `AffirmationId`/`InsightId`/`ReflectionQuestionId` in
  `app/schemas/ai_outcome.py` — a dynamic `Enum` built from the actual
  candidate ids fetched this call, so the AI is structurally incapable of
  returning an id that wasn't really in the filtered list.
- `recommendation.py::build_recommendation()`: replace
  `_fetch_products_stub()` + tag-matching with: fetch candidates for the
  unified colour → call the AI picker with the narrative prompt → for
  each returned id, look up its full record from the fetched candidates
  and build a `RecommendationItem` with `reference_id=id`,
  `title=name`, `image_url=primary_image`, `price=Decimal(price)`,
  `destination_url=f"https://www.giobyquartzic.com/products/{id}"`. Limit
  stays as today (3 for premium, 1 for free).
- **Open question — regeneration frequency.** `build_recommendation` runs
  on *every* check-in and Inner Reading today (cascade.py). Once this
  means a real external HTTP call plus a real AI call, doing that on
  every single check-in (which has no daily cap, unlike Inner Reading's
  weekly free limit) adds real latency and cost to a flow that's supposed
  to feel instant. Worth deciding whether to keep "every submission
  regenerates," or throttle product refresh specifically (e.g., only
  refetch/re-recommend products if the unified colour actually changed
  since the last `RecommendationProfile`, otherwise carry the previous
  items forward). I don't want to silently decide this one, since it's a
  product/cost trade-off, not just an implementation detail.

### Phase 5 — Frontend

No structural changes expected — `ProductCard.tsx` and the recommendation
types already handle real `destinationUrl`/`imageUrl`/`price`/`reason`
end to end (see "Current state" above). The only frontend follow-up is
the pre-existing `$` vs. `MYR` display mismatch noted earlier, which I'd
treat as a small separate fix rather than part of this plan unless you'd
like it folded in.

## Decisions (open questions, resolved)

1. **Colour unification, confirmed as "one colour source."**
   `RecommendationProfile.colour_key` (dynamic, focus-derived) is the
   single source of truth for every product-recommendation purpose — the
   filter API's `elements` param, the narrative prompt, and display.
   Core Personality's `topColourKey` is untouched — it answers a
   different question ("who are you") and isn't part of this plan.
2. **Journal narrative summaries: deterministic**, confirmed. `create_entry`
   stays a plain `def`, no new OpenAI round-trip on journal save — the
   summary is a template like `f"Journaled about {theme.lower()} ({mood.lower()})."`.
3. **Candidate pool size: `per_page=10`**, not 20 — that's the entire
   candidate list the AI picker sees per call.
4. **Regeneration frequency: throttled to once per day per user**, not
   every submission. Concrete mechanism: every check-in/reading still
   creates its own `InnerStateSnapshot` + `RecommendationProfile` row
   (needed for history — nothing about that changes) with its own
   COLOUR/ROUTINE items (cheap, deterministic, unchanged). But the
   expensive part — the live filter-API call and the AI product-picker
   call — runs **at most once per calendar day per user**. Any additional
   submission that same day copies forward that day's already-chosen
   PRODUCT items into its own `RecommendationProfile` rather than
   re-fetching/re-picking. First submission of a new day always
   refreshes.
5. **Fold in the `$`/`MYR` fix, and make recommendations bilingual.**
   Two concrete pieces:
   - **Currency**: `RecommendationItem` has no `currency` column today —
     add one (populated from the filter API's `currency`, currently
     always `"MYR"`). `ProductCard.tsx` formats as `RM {price}` for
     `MYR` and falls back to `{currency} {price}` for anything else,
     replacing the hardcoded `$`.
   - **Bilingual `reason`**: since the AI product-picker (Phase 4) is a
     brand-new call, not a retrofit, it writes `reason_en` **and**
     `reason_zh` directly in the same structured response — genuinely
     bilingual from the start, unlike the older free-generated Inner
     State fields which are still English-only-with-`zh: None`. Storage
     follows the exact convention `InnerStateSnapshot` already uses:
     one JSONB column (`reason`, `{"en": ..., "zh": ...}`) in the DB,
     split into `reason_en`/`reason_zh` at the schema layer
     (`RecommendationItemOut`), same shape as
     `InnerStateSnapshotOut.insight_en`/`insight_zh`. Product `title`
     (the vendor's own product name, already mixed EN/中文 per the
     filter API) and the colour name are display-as-is, not
     translated — only the AI-authored `reason` gets a real second
     language.

## Objectives and deliverables

**Objective:** replace the fully-stubbed product recommendation step with
a real, colour-consistent, memory-grounded, bilingual, cost-bounded
pipeline — without changing check-in/reading submission's reliability
(snapshot/XP/streak/badges must never depend on the vendor API or an AI
call succeeding).

1. **Narrative covers journals** (`app/models/narrative.py`,
   `app/services/narrative.py`, `app/api/v1/endpoints/journal.py`)
   - Add `journal_entry_id` to `NarrativeEntry` + migration; widen the
     single-source check constraint to 3 columns.
   - `create_narrative_entry(..., source_type="JOURNAL")` support.
   - `journal.py::create_entry` writes a deterministic summary narrative
     entry on every journal save.
   - *Done when:* a saved journal entry shows up in
     `recent_narrative_summaries()`'s last-5 output alongside check-ins/readings.

2. **The narrative prompt assembler** (new `app/services/narrative_prompt.py`)
   - `build_narrative_prompt(db, user) -> str`: unified colour + latest
     snapshot dims/focus + last 5 narrative summaries (now cross-source)
     + `build_journal_insights()` rollup, templated per the "mad libs"
     block drafted above.
   - *Done when:* a manual call against a seeded user produces a
     coherent, correctly-filled block with no missing/`None` leaking
     into the text.

3. **Real product fetch** (new `app/services/product_api.py`)
   - Async HTTP client for `GET /api/v1/products/filter?elements={colour}&is_active=true&per_page=10`.
   - Best-effort: any failure/timeout/empty result returns `[]`, never
     raises.
   - *Done when:* a live call against the real API returns parsed
     products with `Decimal` prices, and a simulated failure (bad host)
     degrades to `[]` without throwing.

4. **AI product picker** (`app/schemas/ai_outcome.py` /
   `app/services/ai_outcome.py`, or a new `ai_recommendation.py`)
   - Dynamic `Enum` over the fetched candidate ids (same mechanism as
     `AffirmationId`); structured output includes the chosen ids, each
     with `reason_en` + `reason_zh`.
   - Input: the narrative prompt (item 2) + the ≤10 candidates
     (id/name/price only).
   - *Done when:* the AI never returns an id outside the candidate set
     (structurally impossible by construction) and both reason languages
     are always populated.

5. **Wire it into `build_recommendation`** (`app/services/recommendation.py`,
   `app/models/recommendation.py` + migration for `currency` and the
   `reason` JSONB shape)
   - Once-per-day throttle: check for an existing `RecommendationProfile`
     generated today for this user before hitting the API/AI; if found,
     copy its PRODUCT items forward instead of regenerating them.
   - Replace `_fetch_products_stub()` call site with items 3+4's real
     pipeline when a refresh is due.
   - `destination_url = f"https://www.giobyquartzic.com/products/{id}"`.
   - *Done when:* two check-ins on the same UTC day for one user produce
     identical PRODUCT items; a check-in the next day produces a fresh
     fetch/pick.

6. **Schema + frontend** (`app/schemas/recommendation.py`,
   `gio-member-app/lib/api/types.ts`, `components/ui/ProductCard.tsx`)
   - `RecommendationItemOut`: add `currency`, split `reason` into
     `reason_en`/`reason_zh` (drop the old plain `reason`).
   - `ProductCard.tsx`: render `RM {price}` / `{currency} {price}`
     instead of the hardcoded `$`; select `reason_en`/`reason_zh` by
     the active language the same way `localizedSnapshot` already does
     for Inner State fields.
   - *Done when:* `tsc --noEmit` + `eslint` pass, and a live check-in
     shows a real product card with correct currency formatting and the
     reason text switching with the language toggle.

Verification for the whole plan: seed/reuse a test user, run through
check-in → confirm snapshot/XP/streak/badges still complete even if the
product API is unreachable (simulate by pointing at a bad host
temporarily) → confirm a second same-day check-in reuses that day's
products → confirm the next day's check-in refreshes them → confirm the
frontend renders currency and bilingual reason correctly in both
languages.

## Implementation notes

A meaningful chunk of item 1 and the schema half of item 5 turned out to
already exist, uncommitted, in the working tree by the time I sat down to
build this (`app/models/narrative.py`'s `journal_entry_id` column, the
3-way check constraint, `journal.py`'s narrative-entry wiring, `lock_user`/
`journal_memory` in `narrative.py`, and the `f21d9c8e7012` migration
adding `recommendation_date`/`current_focus_zh`/`summary_zh`/`title_zh`/
`reason_zh`/`currency`). I audited it against this plan via `git diff`
before touching anything further — it matched the decisions above closely
(the `(user_id, recommendation_date)` unique constraint *is* the once-
per-day mechanism, implemented as an upsert-by-day rather than the
copy-forward-into-a-new-row shape I'd originally sketched, which is
cleaner) — verified it, applied the pending migration, and built the rest
on top rather than redoing it.

What shipped, live-verified end to end against a fresh test user
(register → check-in → journal entry → second check-in → Inner Reading,
all same day):

1. **Narrative covers journals** — `journal.py::create_entry` now calls
   `lock_user` then `create_narrative_entry(source_type="JOURNAL", ...)`
   with a deterministic ~20-word verbatim excerpt (`journal_memory()`),
   per the confirmed deterministic-summary decision. Verified via direct
   DB query: a user's `narrative_entries` correctly interleaved
   `CHECK_IN`/`CHECK_IN`/`JOURNAL` rows in chronological order.
2. **`app/services/narrative_prompt.py`** (new) — `build_narrative_prompt()`
   assembles the unified colour + snapshot dims + last-5 cross-source
   narrative summaries + `build_journal_insights()` rollup into the
   templated block. Verified by calling it directly against the test
   user post-journal-entry — the journal excerpt and its mood/theme
   rollup appeared correctly in the "Recent reflections"/"Recent
   journaling" sections.
3. **`app/services/product_api.py`** (new) — `fetch_products_by_colour()`,
   `per_page=10` per the confirmed decision. Verified against the real
   live API (10 real products returned for `elements=scarlet`, real
   prices/images/ids) and against a simulated bad-host failure (returned
   `[]`, raised nothing).
4. **`app/services/ai_recommendation.py`** (new) — `pick_products()`,
   dynamic per-call `Enum` over safe positional keys (`P01`, `P02`, ...)
   rather than the vendor's raw UUIDs (not valid Python identifiers).
   Verified live: picks were genuinely grounded (referenced "emotional
   energy feeling quite low" and "inner pressure elevated" correctly from
   the passed-in dims), and both `reason_en`/`reason_zh` were populated
   with natural, non-literal-translation phrasing in each language.
5. **`app/services/recommendation.py`** rewritten — `build_recommendation`
   now takes `user: User` (not just `user_id`, needed for narrative
   context), looks up today's `RecommendationProfile` by
   `(user_id, recommendation_date)`, and either updates it in place
   (COLOUR/ROUTINE refresh, PRODUCT items untouched) or creates it fresh
   (full pipeline, including the real fetch + AI pick). The async
   fetch/pick calls run via `asyncio.run()` inside this sync function,
   which is safe here because it always executes inside the
   `run_in_threadpool` worker thread `checkins.py`/`readings.py` already
   use — no event-loop conflict. Wrapped in a bare `except Exception` so
   a failure degrades to zero PRODUCT items, never fails the submission.
   `cascade.py`'s call site updated to pass `user=user`. Verified with 3
   consecutive same-day submissions for one test user (check-in →
   check-in with very different dims → Inner Reading): **one**
   `RecommendationProfile` row throughout (same `id` all 3 times),
   COLOUR/ROUTINE correctly flipping with each new focus, the single
   PRODUCT item (a real Sunstone bracelet) identical and untouched across
   all 3 — confirming the once-per-day throttle works across both
   trigger types. `list_recommendations` (the "colour history" feature)
   correctly showed exactly 1 row, not 3, as a natural side effect of the
   upsert.
6. **Schema + frontend** — `RecommendationItemOut`/`RecommendationOut`
   gained `currency`/`title_zh`/`reason_zh`/`current_focus_zh`/
   `summary_zh`/`colour_name_zh` (backend + `lib/api/types.ts`).
   `ProductCard.tsx` takes a `language` prop, selects `reasonZh`/`titleZh`
   when set, and formats `RM {price}` for MYR / `{currency} {price}`
   otherwise, replacing the hardcoded `$`. Both real call sites
   (`dashboard.tsx`, `colour-psychology/index.tsx`) updated to pass the
   new fields and the active language; the legacy mock-data page
   (`pages/recommendation.tsx`, `AppStateContext`-backed, unrelated to
   this real pipeline) needed no changes since the new fields are all
   optional. `tsc --noEmit` and `eslint` clean; both pages return 200
   against the live dev server.

Also added, needed to actually populate the new `_zh` columns:
Chinese translations for the 5 `FOCUS_COPY` entries (`focus_zh`/
`summary_zh`), the 5 `COLOURS` names (`name_zh`), and the 5
`FOCUS_TO_COLOUR` routines (`routine_zh`) in `content.py` — all
deterministic, matching the existing curated-library convention, not
AI-written.

Not done, deliberately out of scope per the plan: no changes to the
`colour-psychology`/`core-personality` pages' own UI text (headings,
static copy) — "dual language" here means the recommendation *content*
(reason, focus, colour name, routine), not a full i18n pass on pages that
were never part of the earlier translation sweep.
