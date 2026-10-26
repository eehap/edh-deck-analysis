# Browser fetch path for blocked networks

Use this when the sandbox shell can't reach the data sites (proxy `403` / `CONNECT tunnel failed`, or the scripts print `Cannot reach … allowlisted`) but a browser tool is available. Each snippet runs `fetch()` inside a page of the right site, returns compact JSON in the exact shape a script accepts, and splits it into ~24 KB chunks because tool outputs get truncated. Nothing has to be reshaped by hand.

Tested live on 2026-10-23 with a 100-card Moxfield deck, and re-checked on 2026-10-26: deck 93/93 entries, Scryfall 93/93 resolved by ID, Oracle Tags bulk available as `jsonl_download_uri`, EDHREC 200 from a moxfield.com page, and Spellbook refused from moxfield.com but working from commanderspellbook.com (2 complete combos, 44 one card away).

## Which page each request must run on (observed CORS behaviour, Oct 2026)

| Data | Endpoint | Works from | Snippet | Feeds |
|---|---|---|---|---|
| Deck list | `api2.moxfield.com/v3/decks/all/<id>` | a **moxfield.com** page only | `edh-deck-intake/scripts/browser/moxfield_deck.js` | `parsed.json` → `enrich.py` / `pipeline.py --parsed-json` |
| Card data + oracle tags | `api.scryfall.com/cards/collection` (75 per call, 2 calls/s), bulk Oracle Tags | **any** origin | `edh-deck-intake/scripts/browser/cards_scryfall.js` | `enrich.py --cards-json` / `pipeline.py --cards-json` |
| Combos + bracket estimate | `backend.commanderspellbook.com/find-my-combos/`, `/estimate-bracket/`, `/card-list-from-url` | a **commanderspellbook.com** page only (other origins fail with "Failed to fetch") | `edh-combo-finder/scripts/browser/combos_spellbook.js` | `find_combos.py --response` / `pipeline.py --spellbook-response` |
| EDHREC stats + candidates | `json.edhrec.com/pages/commanders/<slug>.json` | **any** origin (tested from edhrec.com and moxfield.com) | `edh-cut-add/scripts/browser/edhrec_candidates.js` | `candidates.py --edhrec-json` / `pipeline.py --edhrec-json` |
| Per-gap candidates | `api.scryfall.com/cards/search` | **any** origin | `edh-cut-add/scripts/browser/scryfall_search.js` | `candidates.py --candidates-json` |
| Card data for the user's collection (optional) | `api.scryfall.com/cards/collection` + Oracle Tags bulk | **any** origin | `edh-cut-add/scripts/browser/collection_cards.js` (after the `window.COLLECTION` lines from `collection.py to-js`) | `candidates.py --collection-cards` / `pipeline.py --collection-cards` |

Browsers can't set a custom User-Agent, so Spellbook can't identify the tool by name. Keep to one call per deck, and keep the Spellbook credit in the report.

## The chunk workflow (same for every snippet)

1. Open the page the table says (for Moxfield, the deck's own URL).
2. Run the snippet's contents with the browser's JavaScript tool. It returns `chunks=N bytes=B …`.
3. Evaluate `window.__edh[0]`, then `window.__edh[1]`, … one per call. Save each result **verbatim, including the surrounding quotes**, to `part-0.txt`, `part-1.txt`, …, using a file-writing tool. Don't edit, reformat or unescape anything.
4. Join and validate the parts:
   ```
   python scripts/edh_common.py join cards.json part-*.txt
   ```
   This unquotes each chunk, concatenates them in numeric order, and fails loudly if the JSON is broken (a chunk was truncated or mis-copied). To check one part, `json.loads` it and confirm its length is 24000 (the last part is shorter).

Typical sizes for a 100-card deck: deck 5 KB (1 chunk), cards with tags 31 KB (2), combos 20 KB (1), EDHREC with 40 candidates 27 KB (2).

## Order of operations

1. **Deck** (moxfield.com tab): run `moxfield_deck.js` → `parsed.json`. It also leaves the deck, with Scryfall IDs, in `window.__edhDeck`.
2. **Cards** (same tab): run `cards_scryfall.js` → `cards.json`. It resolves by Scryfall ID, so there are no name mismatches, and attaches oracle tags.
   - Not on Moxfield (pasted list)? Parse it locally with `parse_decklist.py`. Then print the deck for the browser with `python scripts/edh_common.py names-js parsed.json` and run that `window.DECK = …;` line in any tab before the snippet.
3. `python scripts/enrich.py parsed.json --cards-json cards.json --no-api -o deck.json`
4. **Combos** (commanderspellbook.com tab): set `DECK_URL` in `combos_spellbook.js` to the deck URL (Spellbook reads Moxfield, Archidekt, Deckstats and TappedOut itself), or run the `window.DECK = …;` line first. Output is `spellbook.json`, used as `find_combos.py --response spellbook.json`.
5. **EDHREC** (any tab, edhrec.com preferred): set `SLUG`, optionally run `window.DECK = …;` first so deck cards come back as stats rather than candidates. Output is `edhrec.json`, used as `candidates.py --edhrec-json edhrec.json`.
6. **Gaps** (any tab): if `candidates.py` printed `window.QUERIES = …;`, run that line, then `scryfall_search.js`. Output is `supplied.json`, used as `candidates.py --candidates-json supplied.json`.
7. **Collection** (optional, any tab): run the lines printed by `python edh-cut-add/scripts/collection.py to-js my_collection.csv --deck deck.json` (names in ~20 KB parts, deck cards and basics removed), then `collection_cards.js`. It keeps only cards inside the deck's colour identity that are legal, capped at the 250 most-played, with oracle tags. Output is `owned.json`, used as `candidates.py --collection my_collection.csv --collection-cards owned.json`. Tested 2026-10-26: 27 names in, 23 kept, 1 chunk (9.8 KB).

## Formats the scripts accept

- **Card table** (`edh-cards-table/1`): `{"fields": [...], "rows": [[...], ...]}`. Strings for `color_identity`/`produced_mana`, flattened `legal_commander` and `usd`, `card_faces` as `[name, mana_cost, type_line, oracle_text]` rows. `edh_common.expand_cards` turns it back into slim cards; extra fields such as `otags`, `synergy`, `inclusion_rate` and `role_hint` pass through.
- **Slim card** (`edh_common.slim_card`): `oracle_id, name, layout, mana_cost, cmc, type_line, oracle_text, color_identity, produced_mana, legalities.commander, game_changer, prices.usd, card_faces[name, mana_cost, type_line, oracle_text]`, plus optional `rarity, edhrec_rank, otags`. Use this if you assemble cards yourself.
- **parsed.json**: `{"entries": [{"qty", "name", "board"}], "warnings": []}`; board is commander / companion / main / sideboard / maybeboard.
- **Spellbook response**: `{"results": {"identity", "included": [...], "almostIncluded": [...]}, "estimate_bracket": {...}}` with Spellbook's own variant fields, slimmed (no image URLs; near-combos without step text).

## When the browser can't help either

- Moxfield deck private, or no browser: ask for the pasted export.
- Spellbook unreachable: say combo detection couldn't run, and list only combos you're sure of as "from memory, unverified".
- EDHREC unreachable: use the per-gap Scryfall queries `candidates.py` prints, or `--extra` names from your own knowledge, and say so.
