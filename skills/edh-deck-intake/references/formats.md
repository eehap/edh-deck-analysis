# Decklist formats and deck-fetching endpoints

Research snapshot: October 2026. Items marked *(unverified)* came from general knowledge, not a primary source; test them with a real export when a parse looks off.

## Contents
1. Text export formats
2. Fetching by URL
3. Name normalization

## 1. Text export formats

### MTG Arena
Sections `Commander`, `Companion`, `Deck`, `Sideboard`, separated by blank lines. In an unlabelled list, block 1 is the main deck and block 2 the sideboard. Lines are `qty Name` or `qty Name (SET) collector#`. Arena needs both set and number to pin a printing and rejects leading zeros on collector numbers (Draftsim, "How to Import and Copy Decks into MTG Arena"). No foil marker. Alchemy rebalanced cards use an `A-` prefix *(unverified)*.
```
Commander
1 Alela, Artful Provocateur (ELD) 324

Companion
1 Lutri, the Spellchaser (IKO) 227

Deck
1 Temple of Silence (M20) 256
6 Plains (ELD) 251
```

### Moxfield ("Copy for Moxfield")
`<qty> <name> (<SET>) <collector#> *F*` — `*F*` foil, `*E*` etched, `*A*` alter, `#tag` / `#!globaltag` user tags (Moxfield primer gist). Foil markers break naive parsers (Forge issue #11005).
```
Commander
1 Atraxa, Praetors' Voice (2X2) 190 *F*

Deck
1 Delighted Halfling (LTR) 158 *F* #Ramp
```
Moxfield's internal JSON has boards `mainboard`, `sideboard`, `maybeboard`, `commanders`, `companions`, `attractions`, `stickers`, `signatureSpells`; v3 nests them under `boards.<name>.cards`. Each entry has `quantity`, `finish`, `card.{name,set,cn,scryfall_id}`.

### Archidekt
Text: `1x Card Name (set) 123 [Category]` *(unverified syntax)*. Categories can carry flags like `[Maybeboard{noDeck}{noPrice}]`; labels look like `^Have,#37d67a^`. Categories "Commander", "Maybeboard", "Sideboard" move a card off the main board. JSON rows can include removed cards with `deletedAt` set; skip them (wmhunter96/MTG PR #8, Oct 2026).

### MTGO *(unverified)*
`.txt`: `qty name` lines, blank line, then the sideboard; the commander usually sits in the sideboard. `.dek`: XML `<Cards CatID=… Quantity=… Sideboard="true|false" Name=…/>`. No set codes or foil markers. A 1–2 card sideboard in a 100-card list is the commander.

### Plain text and others
`qty name` per line; accept `1`, `1x`, `x1`, trailing `x1`; headers such as `Commander:`, `Commanders`, `EDH`, and type headers (`Creatures`, `Lands`) (decklist.gg import docs). TappedOut marks the commander with `*CMDR*`; Deckstats with `# !Commander`.

## 2. Fetching by URL

| Site | Status | Endpoint | Notes |
|---|---|---|---|
| Commander Spellbook | Official | `GET https://backend.commanderspellbook.com/card-list-from-url?url=…`; `card-list-from-text` for pasted text | Parses Moxfield, Archidekt, Deckstats, TappedOut. Try first. Response shape assumed `{commanders:[{card,quantity}], main:[…]}`; confirm at `/schema/swagger/` |
| Moxfield | No official API (Moxfield FAQ) | `GET https://api2.moxfield.com/v3/decks/all/{publicId}` | `v2/users/{user}/decks` returns 404 since Aug 2026. Concurrent requests return empty bodies: ≤1 req/s. Cloudflare checks; login behind Turnstile, cannot be scripted |
| Archidekt | Semi-official (staff answer on forum; no docs or terms) | `GET https://archidekt.com/api/decks/{id}/` | `/small/` deprecated; `api/decks/cards/?owner=` errors (Oct 2026); list endpoint `/api/decks/v3/?ownerUsername=` caps at 1,000 |

No published terms of use were found for Moxfield or Archidekt automated access. Treat both as personal, low-volume, cached and liable to break; never bulk-crawl.

## 3. Name normalization

1. NFKD, strip accents, unify curly quotes/apostrophes and dashes, collapse whitespace, lowercase (`edh_common.norm_name`).
2. Strip `*F*`, `*E*`, `*A*`, `#tags`, `[Category]`, `^label^` before lookup; keep set, collector number and finish as metadata.
3. `Front // Back` cards: match the full name, the front face, or (for split cards) either face.
4. `A-` prefixed names and `digital: true` cards without paper printings: flag as not paper-legal.
5. Universes Beyond: match `flavor_name` / `printed_name`, store the oracle name.
6. Resolve every line to an `oracle_id`; Commander Spellbook also accepts oracle IDs anywhere it takes a card.
