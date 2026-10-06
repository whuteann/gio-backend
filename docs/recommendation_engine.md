# The recommendation engine — how it works today

A reference audit, written before a round of changes to the engine and its
results — so the "before" state is on record. Covers: what triggers a
recommendation, what's deterministic vs. AI-generated, what gets persisted,
what the API returns, and how each frontend surface actually consumes it
(including a couple of inconsistencies found along the way).

## 1. What triggers it

A recommendation is (re)built as a side effect of finishing a check-in or
an Inner Reading — never on its own, never on a schedule. The call chain:

```
POST /check-ins or POST /inner-readings
  -> app/services/cascade.py :: apply_reflection_side_effects()
       (awards XP, updates streaks/badges, writes the InnerStateSnapshot)
       -> app/services/recommendation.py :: build_recommendation()
```

`build_recommendation` needs: the triggering `InnerStateSnapshot`, a
`focus_key` (see §2), the user's Core Personality id (nullable — a user
can check in before finishing onboarding), which reflection type/id
triggered it, and whether the user is Premium (`is_premium_active`).

### The one-per-day rule

`RecommendationProfile` is a **daily** artifact, not a per-submission one.
Key fact, straight from the model's own docstring intent: at most one live
product fetch + AI pick happens per user per UTC calendar day.

- A user's **first** check-in/reading of a new day creates a fresh
  `RecommendationProfile` row (unique on `(user_id, recommendation_date)`)
  and runs the full pipeline below.
- Any **later** submission that same day updates the same profile's
  COLOUR/ROUTINE items (cheap, deterministic — recomputed every time,
  since there's no reason not to reflect the latest focus) but leaves its
  PRODUCT items **untouched**, carried forward rather than re-fetched/
  re-picked — unless the first attempt that day never actually produced
  any PRODUCT items (vendor API down, AI hiccup), in which case a later
  submission gets one more try rather than being stuck with zero for the
  rest of the day.

## 2. Two halves: deterministic, then AI

### 2a. Deterministic half — colour + routine

Runs first, always succeeds (no network call, no AI), computed in
`build_recommendation` itself from a small static lookup chain:

1. **`resolve_focus_key(dims)`** (`app/services/scoring.py:50-59`) — takes
   the snapshot's 4 dimension scores (0-100 each) and converts each into a
   "need" (how far from ideal): `100 - emotional_energy`, `100 -
   mental_clarity`, `inner_pressure` as-is (high pressure = high need),
   `100 - grounding`. Sorts descending, and if the single biggest need is
   **≥ 55**, that dimension's key wins outright — a hard threshold, winner
   takes all, no weighting between dimensions. Below 55 everywhere, the
   result is `"balanced"`.
2. **`FOCUS_COPY[focus_key]`** (`app/services/content.py:23-49`) — a
   static dict of 5 entries (one per dimension + `"balanced"`) giving the
   bilingual `focus`/`focus_zh` label (e.g. *"Rebuilding energy"* /
   *"重建能量"*) and `summary`/`summary_zh` sentence shown as
   `RecommendationProfile.current_focus`/`.summary`.
3. **`FOCUS_TO_COLOUR[focus_label]`** (`content.py:259-265`) — maps that
   *label* (not the key — a quirk worth knowing) to one of the 5 brand
   colours plus a bilingual routine suggestion string. `"balanced"` →
   Gold; `"Rebuilding energy"` → Scarlet; `"Finding clarity"` → Ocean;
   `"Releasing pressure"` → Forest; `"Regaining grounding"` → Russet.
4. **`COLOURS[colour_key]`** (`content.py:205-256`) — the full colour
   catalog entry (name, swatch hex, traits, description, affirmations,
   positive/negative trait lists) — this is also what backs the standalone
   `/colours` catalog endpoints and the Colour Psychology detail pages,
   not something generated per-recommendation.

Two items get written from this, always, every time `build_recommendation`
runs (rank 1 and 2):
- `type="COLOUR"` — title/reason from the colour catalog + focus label.
- `type="ROUTINE"` — title from `FOCUS_TO_COLOUR`'s routine string, reason
  a template sentence naming the user's Core Personality title if known.

**Source-of-truth note** (confirmed earlier this session): the colour this
whole chain resolves to is written to `RecommendationProfile.colour_key`
and denormalized onto `InnerStateSnapshot.colour_key` too — that field is
the single source of truth for "today's matched colour" anywhere in the
app. It is **unrelated** to Core Personality's own static colour-affinity
score (`CorePersonality.{scarlet,russet,gold,forest,ocean}_score`, computed
once at onboarding from numerology) — two genuinely different systems that
happen to share a 5-colour palette.

### 2b. AI half — product picks

Runs only if 2a succeeded and only on the "first submission of the day"
path (or a retry if that first attempt got zero products). Three steps:

1. **Fetch candidates** — `app/services/product_api.py::fetch_products_by_colour(colour_key)`.
   Plain HTTPS GET to the vendor's real product-filter API
   (`api.giobyquartzic.com/api/v1/products/filter`), filtered by the
   resolved colour key, up to 10 candidates, MYR pricing. Best-effort: any
   failure (timeout, non-2xx, bad shape) returns `[]` rather than raising
   — a down vendor must never block the check-in/reading submission
   itself from completing.
2. **Build grounding context** — `app/services/narrative_prompt.py::build_narrative_prompt()`.
   A single templated block of facts assembled in code (not left for the
   AI to invent): the focus label + colour name/traits, the triggering
   snapshot's 4 raw dimension scores, the last 5 `NarrativeEntry`
   summaries (spanning check-ins, readings, *and* journal entries,
   oldest→newest), and a one-line rollup of this week's journaling
   (entry count + delta vs. last week, top mood, top theme).
3. **Pick + write** — `app/services/ai_recommendation.py::pick_products()`.
   Structured-output call (`responses.parse`, no `temperature`) under a
   "devoted letter-writer" persona. Candidates are keyed `P01, P02, ...`
   (positional, not the vendor's real UUIDs) and wrapped in a
   dynamically-built `Enum`, so the model is structurally incapable of
   returning a candidate that wasn't actually in this call's list. Must
   pick 1 to `limit` (**3 for Premium, 1 for Free** —
   `recommendation.py:105`), ranked best-fit-first. For each pick, the
   model writes:
   - `reason_en` / `reason_zh` — 2-3 sentences, styled as a line lifted
     from a personal letter (sincere, addressed gently, grounded in the
     inner-state/reflection context above) — genuinely bilingual, not a
     translation of one into the other.
   - `material_tag` — a short (1-4 word) cleanly-cased stone/material
     name, English only, extracted from the candidate's (bilingual,
     vendor-supplied) name — e.g. `"苔藓玛瑙 | MOSS AGATE"` → `"Moss Agate"`.
   
   **Fallback**: structured output has no hard non-empty-list guarantee —
   confirmed empirically (two identical back-to-back calls, one picked,
   one didn't). If the model returns zero picks, code falls back to the
   first `limit` candidates verbatim with a plain templated reason
   (`"A {name} matched to your current colour."`) and a code-side
   `_guess_material()` (same bilingual-name-split heuristic, no AI).

Each successful pick becomes one more `RecommendationItem`, `type="PRODUCT"`,
ranked starting at 3 (after COLOUR/ROUTINE), carrying `image_url`, `price`,
`currency`, and a `destination_url` built from the vendor's own product id.

## 3. What's persisted

Two tables (`app/models/recommendation.py`):

**`RecommendationProfile`** — one row per `(user_id, recommendation_date)`.
`current_focus`/`current_focus_zh`, `summary`/`summary_zh`, `colour_key`,
`status`, `generated_at`, plus FKs back to the triggering snapshot/Core
Personality/check-in-or-reading. `items` is a relationship ordered by
`rank`.

**`RecommendationItem`** — one row per colour/routine/product entry.
`type` (`COLOUR | ROUTINE | PRODUCT`), `reference_id` (colour key or
vendor product id), `title`/`title_zh`, `reason`/`reason_zh`, `rank`,
`image_url`, `price`, `currency`, `destination_url`, `material_tag`
(PRODUCT-only; null on COLOUR/ROUTINE).

## 4. What the API returns

`GET /recommendations/latest` and `GET /recommendations` (list, Premium
gets full history, Free capped to 1) — `app/schemas/recommendation.py`:

```
RecommendationOut
  id, current_focus(_zh), summary(_zh)
  colour_key, colour_name(_zh), colour_swatch   # resolved fresh from COLOURS at read time
  status, generated_at
  items: [RecommendationItemOut]
    type, reference_id, title(_zh), reason(_zh), rank,
    image_url, price, currency, destination_url, material_tag
```

## 5. How the frontend actually consumes this — including two inconsistencies

Three surfaces read `items`, and they don't all treat it the same way:

- **`colour-psychology/index.tsx`** (the main "Recommended for You" page,
  redesigned earlier this session) — filters `items` down to
  `type === "PRODUCT"` only and renders those through `ProductCard` as a
  vertical list (colour pill + material pill + letter-style quote). COLOUR
  and ROUTINE items are fetched but never shown here at all.
  **Known bug, not yet fixed**: this page's "current colour" header card
  does *not* read `recommendation.colour_key` — it re-derives a colour
  from `recommendation.current_focus` via a second, independent frontend
  mapping table (`colourKeyForFocus`, in the legacy `lib/recommendation.ts`
  mock file). Two mapping tables that happen to agree today, not one
  shared source of truth.

- **`dashboard.tsx`**'s "For You" card — takes `recommendation.items.slice(0, 3)`
  with **no type filter at all**. Since items are ordered by rank
  (COLOUR=1, ROUTINE=2, PRODUCT=3+), this card renders the COLOUR item and
  the ROUTINE item through the same `ProductCard` that was designed for
  PRODUCT items — so a Free user (who only ever gets 1 PRODUCT item) sees
  "Ocean" (colour) and a routine instruction rendered as if they were
  products, each missing a material pill (always null for these types),
  before the one real product shows up third.

- **`pages/recommendation.tsx`** — a separate, apparently-legacy page:
  finds the single COLOUR item and ROUTINE item explicitly and renders
  them in their own cards, and lists PRODUCT items through a *bare*
  `<ProductCard item={item} />` with no `colourName`/`colourSwatch`/
  `materialTag` props wired through (pre-dates that redesign). Still says
  *"Matched from the Gio store"* (the external commerce brand name, not
  touched in the Auren rebrand on purpose — see that work's notes). Not
  linked from primary nav as far as this audit found; unclear if it's
  still reachable/used or dead code.

## 6. Open questions worth settling before changing the engine

- Is `dashboard.tsx`'s unfiltered `slice(0, 3)` intentional (show the full
  "signature" of today's recommendation) or a bug (should filter to
  PRODUCT like `colour-psychology` does)?
- Is `pages/recommendation.tsx` still live/linked anywhere, or safe to
  delete/ignore?
- The `colourKeyForFocus` duplicate-mapping bug on `colour-psychology/index.tsx`
  — in scope for this round of changes, or separate?
