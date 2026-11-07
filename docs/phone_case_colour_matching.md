# Colour-first casing recommendations

Agreed behaviour: **recommended colour → matching artwork → suitable design**.
AI ranks designs only inside the colour-matched pool. It cannot substitute a
different colour because its name or story fits the mood. No match means no
casing recommendation; the UI explains this in English, Chinese and Malay.

## Colour data

The merchant can maintain Shopify product metafield `custom.auren_colour_keys`,
type `list.single_line_text_field`, containing Auren keys:

| Key | Artwork colour family |
| --- | --- |
| scarlet | Red |
| russet | Earthy brown-red |
| gold | Gold/yellow |
| forest | Green |
| ocean | Blue/teal |

Example value: `["forest"]`. Use the main artwork colour; an incidental accent
does not automatically qualify. An explicit empty list excludes the design.
Invalid values fail closed. No names, descriptions or images are classified by
the recommendation model. Standard `shopify.color-pattern` references returned
null with this installation's current access and are not mapped from opaque IDs.

For the initial catalogue, `phone_case_colours.py` records three reviewed
products, bound to the exact featured image URL/version inspected on
2026-11-07. Their images and merchant descriptions agree:

| Product | Shopify product ID | Key | Description evidence |
| --- | --- | --- | --- |
| Blue Stillness | 10114644869417 | ocean | “The Blue Tree” |
| Rooted Ascent | 10114653389097 | forest | “Green symbolizes life, hope” |
| Rooted Growth | 10114691727657 | forest | “Green symbolizes life, growth” |

Other products stay excluded until explicitly labelled/reviewed. Pink, purple,
orange and black/white do not automatically become red, gold or brown. At this
review there are **no classified Scarlet, Russet or Gold casing matches**.
An image change invalidates a reviewed fallback; explicit merchant metadata
takes precedence. Adding the metafield to a new design requires no code change.
The catalogue refreshes lazily every 24 hours; pre-colour caches refresh on
their next read. A partial/failed Shopify response preserves the prior cache.

## Selection and saved recommendations

- A matching pool is built before AI receives candidates, with a second
  colour filter inside the AI service. Its structured-output enum contains
  only eligible IDs. Design descriptions help the second-stage selection.
- Reasons explain colour match first, then design suitability, in all three
  languages. Case selection works even if no matching stone is available.
- Daily stone picks and their letter remain stable. Cases are reselected if
  the displayed colour changes, or once to upgrade old unclassified picks.
- Successful same-colour casing picks remain stable. Missing matches/model
  failures retry after ten minutes. A catalogue change removes invalid picks.
- API serialization validates cases against the cached colour data even for
  historical/by-ID responses; old mismatched cases cannot leak through.
- `phone_case_status`: `READY` (valid picks), `NO_MATCH` (processed catalogue has
  no colour match), `UNAVAILABLE` (catalogue/selection unavailable).

## Release and rollback

Additive migration `e308ca517b42` follows `d706da913b21`. Apply it before the
code checkout changes because the production bind mount reloads immediately.
It adds nullable cache metadata and case-selection tracking; it does not
rewrite or delete user readings, stones or historical recommendations.
Old code can run with the extra columns if rollback is needed.

Regression tests: `tests/test_phone_case_colours.py`; PostgreSQL tests refuse
any database except explicitly configured `auren_colour_qa`. Use staged code
outside `/app`, disable the language worker, and never run the integration
suite against production. All vendor/model calls in the suite are mocked.
