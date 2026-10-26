# Data sources: access, staleness, licensing

| Source | Status | Use | Limits / terms |
|---|---|---|---|
| Scryfall API + bulk | Official, free | card data, oracle tags, prices, candidate search | 2 req/s on search/named/collection/random, 10/s otherwise; 429 → 30 s lockout, repeated abuse → ban; descriptive User-Agent; no paywalling, no implied endorsement |
| Commander Spellbook | Official, documented, open source | combos, near-combos, bracket hints, URL decklist parsing | ≤ ~80 req/min, handle 429, named User-Agent, credit + link required; use bulk file for whole-dataset needs |
| EDHREC | Unofficial JSON | synergy, inclusion, candidates | terms not found; low volume, cache 24 h, attribute, don't redistribute |
| Moxfield | No official API | fetch deck by URL | Cloudflare/Turnstile; endpoints changed Aug 2026; ≤1 req/s; terms not found |
| Archidekt | Semi-official | fetch deck by URL | undocumented; terms not found |

## Blocked sandbox networks
Cloud sandboxes often refuse all four hosts at the proxy (`CONNECT tunnel failed, response 403`). The supported workaround is a browser tab running the snippets in `browser_fetch.md` (tested 2026-10-23 and re-checked 2026-10-26):
- Scryfall and EDHREC answer cross-origin requests from any page.
- Moxfield's api2 needs a moxfield.com page.
- Commander Spellbook needs a commanderspellbook.com page.

## Staleness
- Bracket rules and Game Changers: beta, can change at any announcement. Version and date them (`bracket_rules.json`).
- Scryfall prices: stale after 24 h. Oracle tags: change daily. Card data: weekly refresh is enough.
- EDHREC synergy lags for new sets.
- Spellbook adds combos continuously; note when the data was fetched.

## Licensing
- Card text and images: Wizards of the Coast, under its Fan Content Policy.
- Scryfall data: not behind paywalls, not presented as Scryfall-endorsed; credit artists when showing art.
- Spellbook: credit and link back.
- Prior-art code (infernal-machine, mtg_deck_analyzer, pyedhrec, Scrython…): licenses unverified; check before reusing code.

## Needs model judgment, not rules
On-plan vs off-plan, win-more, conditional ramp, engine vs one-shot draw where tags are silent; combo outlet availability and whether a combo is "early" for Bracket 3; intent-based bracket placement; final cut/add rationale.

## Unverified in the research (Oct 2026)
MTGO and Archidekt text-export syntax; Spellbook response fields beyond `included/almostIncluded/uses/produces/bracketTag/manaNeeded/identity/legalities/popularity`; the blue Game Changers entries; current Oracle Cards bulk size; whether the ~Oct 12 2026 B&R announcement touched Commander.
