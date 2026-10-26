# Commander Spellbook API notes (October 2026)

- Base: `https://backend.commanderspellbook.com/`. Root lists `variants`, `features`, `cards`, `templates`, `find-my-combos`, `estimate-bracket`, `explain-query`, `card-list-from-url`, `card-list-from-text`.
- OpenAPI schema at `/schema/`, Swagger UI at `/schema/swagger/`. Responses are camelCase.
- Generated clients: Python `spellbook_client`, TypeScript `@space-cow-media/spellbook-client`.
- Bulk: `https://json.commanderspellbook.com/variants.json.gz`, all variants and aliases. "Do not use the HTTP API to export the whole dataset."
- Developer guidelines (backend docs, updated Oct 19 2026): name your service in the User-Agent; "80 requests per minute should be a safe rate"; always handle 429; "Please credit us and link back to commanderspellbook.com."
- Open source: SpaceCowMedia/commander-spellbook-backend (Python/Django).

## find-my-combos

```
POST https://backend.commanderspellbook.com/find-my-combos/
Content-Type: application/json
User-Agent: edh-deck-skills/1.0
{"commanders":[{"card":"Kinnan, Bonder Prodigy","quantity":1}],
 "main":[{"card":"Basalt Monolith","quantity":1},{"card":"Sol Ring","quantity":1}]}
```
Cards may be names or oracle IDs.

```
{"results":{
  "identity":"GU",
  "included":[{"id":"…","uses":[{"card":{"name":"Kinnan, Bonder Prodigy"}},{"card":{"name":"Basalt Monolith"}}],
     "produces":[{"feature":{"name":"Infinite colorless mana"}}],
     "bracketTag":"…","manaNeeded":"{3}","identity":"GU","legalities":{"commander":true},
     "popularity":12345,"easyPrerequisites":"…","notablePrerequisites":"…","description":"1. … 2. …"}],
  "almostIncluded":[…one card missing…],
  "includedByChangingCommanders":[…], "almostIncludedByAddingColors":[…]}}
```
**Verified** (third-party project, 2026-10-21): `included`, `almostIncluded`, `uses`, `produces`, `bracketTag`, `manaNeeded`, `identity`, `legalities`, `popularity`.
**Verified 2026-10-26** against `/schema/?format=json`: `BracketTagEnum` = R Ruthless, S Spicy, P Powerful, O Oddball, C Core, E Exhibition, B Banned. This is Spellbook's own scale, not the official 1–5 brackets.
**CORS (tested 2026-10-23 and 2026-10-26)**: `find-my-combos`, `estimate-bracket` and `card-list-from-url` answer only pages on commanderspellbook.com; from other origins `fetch` fails with "Failed to fetch". See `browser_fetch.md`.
**Not verified**: the other buckets, `easyPrerequisites`/`notablePrerequisites`/`description`, `requires` (templates), pagination via `next`. `find_combos.py` reads them defensively; check `/schema/` if output looks empty.

Variants also carry a community `salt` score (0–4; shown once there are ≥5 votes in the past year).

`almostIncluded` is exactly one card away. Two-or-more-away needs the bulk file and local set matching (`--two-away`).

## estimate-bracket

Announced by the Spellbook backend developer on Moxfield's feedback board; returns "bracket-relevant information, mainly two card combos classified based on their requirements". Moxfield ships a Spellbook-backed bracket integration. The request/response schema was not verified; `edh-deck-review/scripts/bracket_floor.py --spellbook` stores whatever comes back as raw data.

## Prior art worth knowing
- jeisenback/infernal-machine: cached Spellbook client keyed by sorted card names; single-card bracket rules + Spellbook for combos.
- Combinator (jamese.dev): Spellbook stopped shipping its full database to the client in early 2024. Use the API or the bulk file.
- Melrakkiie/Tamiyo: gzip, User-Agent and a visible credit link.
