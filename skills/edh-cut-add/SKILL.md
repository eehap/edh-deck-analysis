---
name: edh-cut-add
description: 'Recommend which cards to cut from a Magic: The Gathering Commander/EDH deck and what to add instead, as paired swaps with a reason for each — driven by role gaps, mana efficiency, off-plan and high-cost/low-impact cards, bracket rules (Game Changers, mass land denial, two-card combos), budget, and candidates from EDHREC, Scryfall oracle-tag searches, Commander Spellbook near-combos and, optionally, the user''s own card collection (prefer or only use cards they own). Use it whenever someone asks how to upgrade, tune, fix or "make better" their Commander deck, what to take out, what to put in, how to fit a bracket or budget, what they could add from cards they already own, or wants "10 swaps" — even if they don''t say cut or add. Needs deck.json (edh-deck-intake) and structure.json (edh-deck-structure); combos.json (edh-combo-finder) helps.'
---

# EDH cut/add recommender

Scripts rank; you decide. The deterministic pass finds role surpluses and gaps, prices, bracket violations and candidates. Your job is to veto swaps that break the deck's identity, keep the user's pet cards, and explain each swap the way a good playgroup friend would.

## Before you run anything

Know (from the conversation, or ask once): target **bracket**, **budget** per card if any, and any cards the user **won't cut** (pets, theme pieces, cards they just bought). These change the answer more than any weight in the scripts. If the user shared a **collection** (or mentions what they own), find out whether they'd buy cards at all: "only use what I have" is `--collection-mode only`, otherwise `prefer`.

## Workflow

1. **Candidates.** `python scripts/candidates.py deck.json structure.json --combos combos.json --bracket N [--strategy <profile>] [--budget USD] [--edhrec-json edhrec.json] [--candidates-json cards.json] [--extra names.json] [--offline] -o candidates.json`
   - EDHREC commander page (unofficial JSON; cached 24 h): synergy and inclusion rates for candidates *and* for the deck's own cards.
   - Scryfall `otag:` searches for each under-target role, filtered by color identity, legality, budget and Game Changer cap.
   - Spellbook near-combo pieces, only at Bracket 3+.
   - `--edhrec-json`: a saved EDHREC commander page or the browser snippet's output. Use it instead of the live call.
   - `--candidates-json`: cards supplied from outside. Accepts the snippet's card table, slim cards, or full Scryfall cards, each optionally with a `role_hint`.
   - `--extra`: a JSON list of names you want considered. Use it to inject cards you know fit the commander, and as the main source when EDHREC and Scryfall are unreachable.
2. **Swaps.** `python scripts/score_swaps.py deck.json structure.json candidates.json --combos combos.json --bracket N [--protect "Card"]... --max-swaps 10 -o swaps.json --md swaps.md`
   - `must_cut`: Game Changers over the bracket cap, mass land denial or chainable extra turns at Bracket ≤3. Always first.
   - `bracket_conflicts`: two-card combos that don't fit the bracket. The user decides which piece goes (or plays a higher bracket); don't silently pick for them.
   - `swaps`: greedy pairs; role totals update after each swap so the list doesn't pile into one role. All of a card's roles are weighed together. A surplus in one role isn't a reason to cut a card that also fills a role the deck needs. **Engine** cards and **cheated** cards (put into play without casting, marked by the structure skill) are never cut for role surplus or for their mana cost.
   - `cuts_without_a_good_add`: good cuts where no candidate closed a gap. Suggest an add from your own knowledge or leave the slot open.
   - `land_note`: if the mana analysis wants more lands, some cuts should become lands.
3. **Review every swap.** Veto or replace any swap that:
   - cuts a card the commander's plan depends on (a cheap sac outlet in aristocrats scores "no role" if review missed it),
   - adds a card that's strong in general but doesn't fit (EDHREC synergy is popularity-biased),
   - breaks the curve (adding a 5-drop for a 2-drop needs a reason) or the land count,
   - exceeds budget or bracket.
   Write the final list yourself. Each swap gets one or two plain sentences: what the cut doesn't do *here*, what the add does *here*. Cite the card text or the deck's numbers ("you're at 14 ramp against a 8–12 range, and Gilded Lotus is your most expensive rock").

## Collection (optional)

Everything works without one. With `--collection <file>` on `candidates.py` (or phase2 of the review pipeline):

- **Formats:** CSV exports from Moxfield, ManaBox, Deckbox, Dragon Shield, TCGplayer and Archidekt are read by their header row. Plain `qty name` text works too, as does `collection.json` from `python scripts/collection.py parse <file>`. Quantities are summed across printings, and front-face-only names match double-faced cards. Run `collection.py parse` first if you want to check the read: it reports distinct cards, copies and lines it didn't understand.
- **What changes:**
  - Owned cards that fit the deck (identity, legality, Game Changer cap, not already in the deck) become candidates themselves, as source `collection`.
  - Every candidate is marked `owned`.
  - Owned cards skip the `--budget` filter, because adding them costs nothing.
  - Owned near-combo pieces still get their combo credit.
- **Modes:**
  - `prefer` (default) gives owned adds +2. That breaks ties and tips close calls, but never qualifies an add on its own: it still has to close a role gap, bring synergy or complete a combo.
  - `only` drops every candidate the user doesn't own. If that leaves gaps unfilled, say so and list the best cards they'd need to buy, as a separate "if you buy one thing" note.
- **Output:**
  - Swaps show "(owned)" instead of a price.
  - `swaps.md` summarises how many adds are owned and what the rest costs.
  - `deck_cards_not_owned` in `swaps.json` lists deck cards missing from the collection. A long list usually means a partial export, or cards already sleeved in decks being left out. Mention it gently; don't treat it as a problem with the deck.
- **Card data for owned cards** comes from the local Scryfall index, Scryfall's API, or, on a blocked network, the browser:
  1. Run `python scripts/collection.py to-js <file> --deck deck.json` and run the lines it prints in any browser tab. The names go in ~20 KB parts, with deck cards and basics already removed.
  2. Run `scripts/browser/collection_cards.js` in the same tab. It keeps only cards that fit the identity and are legal, capped at the 250 most-played, with oracle tags attached.
  3. Join the chunks and pass `--collection-cards owned.json`.

  Without card data the collection still marks which of the other candidates are owned, and the script prints these steps.
- Ownership is by name. It can't tell whether a copy is already in another deck, so say so when it matters ("you own one copy").

## Heuristics behind the scores (and their limits)

Cut order: role surplus first (most expensive copy first) → off-plan → MV ≥ 6 without a game-winning or game-swinging effect → inefficient for its role → win-more → conditional cards the deck rarely enables → bracket violations (forced). Format staples (top-150 EDHREC rank) are protected a little; combo pieces a lot. Full rationale and sources: `references/heuristics.md`.

EDHREC synergy = this commander's inclusion rate minus the color identity's baseline. It says a card is *characteristic* of the commander, not that it's good: staples score near zero, new cards are noisy, small commanders swing wildly, and the data isn't split by bracket. Use it to find candidates and break ties, never as the reason to cut. `references/edhrec.md` covers the endpoint and its caveats.

## Prices

Scryfall prices are TCGplayer USD (Cardmarket EUR), refreshed daily: label them as estimates with the date from `candidates.json`. If the user cares about cost, total the adds. With a collection, total only the adds they'd have to buy (`swaps.json["collection"]["cost_to_buy_usd"]`).

## When data sources are blocked

When neither EDHREC nor Scryfall search is reachable and nothing was supplied, `candidates.py` prints each role gap with a ready Scryfall query (e.g. `otag:tutor -otag:tutor-land id<=WUBR legal:commander -is:digital`). For cheat profiles it also prints a `hits` query (`t:creature cmc>=6 id<=…`). It then prints a `window.QUERIES = …;` line and stores everything in `candidates.json["queries"]`. Then, in order of preference:

1. **Browser.** EDHREC's JSON and Scryfall's API both answer cross-origin requests, so any tab works; an edhrec.com tab is the polite choice.
   - Run `scripts/browser/edhrec_candidates.js` with `SLUG` set (optionally run the `names-js` `window.DECK` line first), then `--edhrec-json edhrec.json`.
   - Or run the `window.QUERIES` line, then `scripts/browser/scryfall_search.js`, then `--candidates-json supplied.json`.

   Join chunks with `python scripts/edh_common.py join …`. The workflow is in `references/browser_fetch.md`.
2. **Manual search.** Paste the printed queries into scryfall.com/search yourself, if the user can.
3. **Model knowledge.** Build an `--extra` list from your own knowledge of the commander and archetype (respecting identity, bracket and budget), and tell the user the pool came from model knowledge rather than live data.
