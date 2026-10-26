# Scryfall: endpoints, limits, bulk data, oracle tags

Snapshot October 2026. Primary sources: scryfall.com/docs/api (rate limits, bulk data, tags).

## Endpoints and rate limits

| Endpoint | Use | Limit |
|---|---|---|
| `GET /cards/named?exact=` / `?fuzzy=` | single lookup, typo recovery | 2/s |
| `POST /cards/collection` | batch lookup, ≤75 identifiers | 2/s |
| `GET /cards/search?q=` | candidate generation | 2/s |
| `GET /cards/random` | — | 2/s |
| `GET /cards/manifest` | change tracking | 10/min |
| everything else incl. `/bulk-data` | — | 10/s |
| `*.scryfall.io` file hosts | bulk downloads | unlimited |

A 429 locks you out for 30 seconds; repeated abuse "may result in a temporary or permanent ban". Send a descriptive `User-Agent` and an `Accept` header. Several projects hit 429s in Sep–Oct 2026 after the 2/s tier tightened, which is why `edh_common.http` spaces these calls 550 ms apart.

Example:
```
POST https://api.scryfall.com/cards/collection
{"identifiers":[{"name":"Sol Ring"},{"set":"mh3","collector_number":"1"}]}
→ {"object":"list","not_found":[],"data":[{"oracle_id":"…","name":"Sol Ring","mana_cost":"{1}","cmc":1.0,
   "type_line":"Artifact","oracle_text":"{T}: Add {C}{C}.","color_identity":[],"produced_mana":["C"],
   "legalities":{"commander":"legal"},"game_changer":false,"edhrec_rank":1,"prices":{"usd":"1.50"}}]}
```

## Bulk data

- **Oracle Cards** — one object per `oracle_id`; the right file for analysis (148 MB in a Jan 2025 snapshot, larger now).
- **Default Cards** — every English printing; only for printing-level prices.
- **Oracle Tags** — community function tags; 5.76 MB, updated 2026-10-21. Tag objects have a stable `id`, `parent_ids` (hierarchy) and taggings by `oracle_id`. Direct taggings only, so walk `parent_ids` yourself (`scryfall_data.parse_oracle_tags` does). The loader is tolerant because this schema is new; if Scryfall reshapes it, adjust that one function.
- Cadence: regenerated every ~12 h. Weekly (or on set release) is enough for gameplay data. Prices are "dangerously stale" after 24 h.

## Fields used

`oracle_id, name, layout, mana_cost, cmc, type_line, oracle_text, keywords, colors, color_identity, produced_mana, legalities.commander, game_changer, edhrec_rank, prices.{usd,usd_foil,eur,tix}, card_faces[], reserved, digital, rarity`.

`game_changer` (added Feb 2025 with the brackets) means you never need to maintain your own Game Changers list; `is:gamechanger` works in search.

Multi-faced layouts (`transform`, `modal_dfc`, `split`, `adventure`, `flip`): face-level `mana_cost`, `oracle_text`, `type_line` live in `card_faces[]`; top-level `cmc` and `color_identity` describe the whole card. Concatenate face texts for role tagging, except MDFC land faces, which count as a partial land (0.8, or 1.0 for mythic).

## Oracle tags (`otag:`)

Community-maintained, moderated function tags ("removal", "ramp", "draw", "sacrifice-outlet", "tutor-any-card"…), searchable as `otag:` / `oracletag:` / `function:`. They "may be updated or reorganized at any time". No per-card tags endpoint exists; use the bulk file. Coverage evidence: one importer tagged 93% of 38,705 cards across 4,560 tags. An older claim that tags aren't in bulk data is outdated. Aliases (e.g. `blink` → `flicker`) live only in the bulk file.

## Terms (re-read before publishing anything)

Free for creating Magic software, research and community content; don't paywall Scryfall data or put it behind account walls; don't imply Scryfall endorsement; credit artists when showing art crops. Card text and images belong to Wizards of the Coast (Fan Content Policy).
