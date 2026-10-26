---
name: edh-deck-intake
description: 'Parse a Magic: The Gathering Commander/EDH decklist (pasted text, a file, or a Moxfield/Archidekt/TappedOut/Deckstats URL) and resolve every card against Scryfall into a canonical deck.json with oracle text, mana costs, color identity, legality, Game Changer flags, prices and Scryfall oracle tags. Use this whenever someone shares a Commander decklist or deck link and wants anything done with it — analysis, upgrades, combo checks, bracket checks, legality checks, price totals — even if they don''t say "parse" or "import". It is the first step of the edh-deck-review pipeline and the input for edh-deck-structure, edh-combo-finder and edh-cut-add.'
---

# EDH deck intake

Turn whatever the user pasted into one trustworthy file, `deck.json`, that every other EDH skill reads. Getting this step right matters more than anything downstream: a mis-resolved card name silently corrupts role counts, combos and bracket checks.

## Workflow

Scripts live in `scripts/` next to this file. They use only the Python standard library.

1. **Get the list.**
   - Pasted text or a file: save it to `deck.txt`, then
     `python scripts/parse_decklist.py deck.txt -o parsed.json`
     It auto-detects MTG Arena, Moxfield ("Copy for Moxfield", with `*F*` foil and `#tag` markers), Archidekt (`1x Name (set) 123 [Category]`), MTGO `.txt`/`.dek`, TappedOut `*CMDR*` and plain `qty name` lists.
   - A URL: `python scripts/fetch_deck_url.py <url> -o parsed.json`. It tries Commander Spellbook's official `card-list-from-url` first, then Moxfield/Archidekt's unofficial JSON. If all fail (private deck, Cloudflare, sandbox network), use the browser snippet (see "When there is no network") or ask the user to paste the export text. On Moxfield that is More → Export → Copy for Moxfield; on Archidekt, Export → Text.
2. **Check the commander.** Read the warnings. If no commander was identified or one was *inferred*, confirm with the user, then rerun with `--commander "Name"` (repeat it for partners). Do this before going further; every later step keys off the commander's color identity.
3. **Load card data.** `python scripts/scryfall_data.py update` downloads Scryfall's Oracle Cards and Oracle Tags bulk files and builds a slim cached index (refreshes weekly; `--force` after a set release). If the user supplied bulk files, pass `--cards-file`/`--tags-file`.
4. **Resolve.** `python scripts/enrich.py parsed.json -o deck.json`. It uses the local index first, then Scryfall's `/cards/collection` (75 names per call), then fuzzy lookups, offered as *suggestions*, never silently accepted.
5. **Fix problems before handing off.** Show unresolved names with their suggestions and ask, or rerun with `--accept-fuzzy` when the suggestions are obviously typos. Relay legality warnings (banned, off-identity, duplicates, deck size ≠ 100, digital-only cards) plainly; the user may be mid-build, so treat them as information, not errors.

## When there is no network

Sandboxes often block the data sites: the shell gets `CONNECT tunnel failed, response 403`, and the scripts print `Cannot reach … allowlisted`. Don't retry with other shell tools, because they all go through the same proxy. Options, best first:

1. **Browser fetch.** If a browser tool is available (the built-in browser pane or Claude in Chrome), run the ready-made snippets in `scripts/browser/` inside a page of the right site. Each returns compact JSON in exactly the shape a script accepts, split into ~24 KB chunks. Copy each chunk verbatim into `part-N.txt`, then run `python scripts/edh_common.py join <out>.json part-*.txt` to rebuild and validate the file. Never retype or reshape the JSON by hand; that is slow and error-prone.
   - Deck: `moxfield_deck.js` on the deck's own moxfield.com page → `parsed.json`.
   - Cards and oracle tags: `cards_scryfall.js` in the same tab → `cards.json`. Then run
     `python scripts/enrich.py parsed.json --cards-json cards.json --no-api -o deck.json`.

   `references/browser_fetch.md` has the full workflow, which page each request must run on (CORS), and the formats. Combos and EDHREC have their own snippets in edh-combo-finder and edh-cut-add.
2. **Attached bulk file.** If the user can attach Scryfall's Oracle Cards export (`.json`, `.jsonl` or `.jsonl.gz`), use `scryfall_data.py update --cards-file …`.
3. **Ask for an allowlist.** Ask whether they can allow `scryfall.com`, `scryfall.io`, `commanderspellbook.com`, `moxfield.com` and `edhrec.com` in their network settings.
4. **Last resort.** Write slim cards yourself from reliable knowledge, using the schema below, and pass `--cards-json cards.json --no-api`. Say in the report that card data came from model knowledge. Never invent oracle text for a card you don't recognize; leave it unresolved.

`--cards-json` accepts the snippet's card table, `{"cards": [...]}`, full Scryfall cards, or **slim cards**. A slim card has `oracle_id, name, layout, mana_cost, cmc, type_line, oracle_text, color_identity, produced_mana, legalities.commander, game_changer, prices.usd`, plus `card_faces[name, mana_cost, type_line, oracle_text]` for multi-faced cards. Optional extras are `rarity, edhrec_rank, otags`. `edh_common.slim_card` defines the schema.

## deck.json contract

```
schema: "edh-deck/1"
commanders: [names], companion, color_identity: "BG"
cards: [{oracle_id, name, qty, board (main|commander|companion|sideboard|maybeboard),
         is_commander, set, cn, finish, user_tags, otags: [...], card: {slim Scryfall fields}}]
unresolved: [{name, line_no, suggestion}], warnings: [...], counts: {...}
data: {index_built_at, price_date, has_otags}
```
Always store the oracle name, not a Universes Beyond/flavor name; keep set/collector number/finish only as printing metadata (they matter for price, nothing else).

## Name rules worth knowing

- Double-faced, modal DFC, split, adventure and flip cards are `Front // Back` on Scryfall; exports often give only the front face. The index matches either face.
- `A-` names are Alchemy rebalances: digital-only, not legal in paper. Flag them; don't map them to the paper card.
- Universes Beyond printings share the oracle card of their Universes Within twin; the index matches `flavor_name`/`printed_name` too.
- Maybeboard and sideboard cards are kept but excluded from counts.

## Etiquette with data sources

Scryfall caps `/cards/search`, `/cards/named`, `/cards/collection` at 2 requests/second and locks clients out for 30 s on a 429; repeated abuse gets apps banned. `edh_common.http` throttles and backs off automatically, so route all calls through it rather than writing ad-hoc requests. Moxfield and Archidekt have no published API terms: low volume, cached, expect breakage. Credit Scryfall when showing its data, and never imply endorsement.

More detail (format examples, endpoint shapes, field notes): `references/formats.md` and `references/scryfall.md`. Read them when a parse looks wrong or an endpoint misbehaves.
