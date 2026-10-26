---
name: edh-combo-finder
description: 'Find the combos a Magic: The Gathering Commander/EDH deck contains or is one or two cards away from, using Commander Spellbook''s find-my-combos API and bulk data, then score how robust each combo is (piece count, mana, tutor access, redundancy, fragility to removal and graveyard hate, whether it wins outright or needs an outlet). Use it whenever someone asks what combos are in their deck, whether their deck "goes infinite", what single card would complete a combo, whether a combo is too strong for their bracket, or how reliable their win condition is. Needs deck.json from edh-deck-intake; roles.json from edh-deck-structure improves the tutor analysis.'
---

# EDH combo finder

Commander Spellbook does the combo lookup; this skill adds the part a player actually needs: can this deck realistically assemble and win with the combo, and what does it mean for the bracket?

## Workflow

1. `python scripts/find_combos.py deck.json --roles roles.json -o combos.json --md combos.md`
   - One `POST /find-my-combos/` per deck, cached for 24 h by the sorted card list. Returns `included` (all pieces present) and `almostIncluded` (exactly one card missing).
   - `--two-away` also downloads Spellbook's bulk `variants.json.gz` (cached daily) and matches locally for combos missing two cards. The API never returns those.
   - `--source bulk` works fully offline once the bulk file is cached; `--response saved.json` replays a saved API response.
2. Read `combos.json` and check what the rules can't:
   - **Outlets.** For combos whose result is infinite mana, tokens, death triggers or ETBs, the script guesses whether the deck has a way to turn that into a win (`outcome_note`). Verify by reading the cards, and name the outlet.
   - **Prerequisites.** Spellbook's prerequisites (e.g. "another Zombie on the battlefield", "Gravecrawler in graveyard") can make a combo much harder than its piece count suggests. Say so.
   - **Templates.** Some variants require "a sacrifice outlet" or similar rather than a named card (`templates_required`). Check the deck actually has one.
3. Present results with `combos.md` as the base: complete combos ranked by robustness, then the single cards that would unlock near-combos (one add can complete several), then two-away highlights if requested.

## Robustness score (0–100)

| Factor | Weight | How |
|---|---|---|
| Pieces | 25 | 2 pieces 25, 3 → 15, 4+ → 5; +5 if the commander is a piece (always available) |
| Mana | 15 | piece MV (excluding commander) + mana needed; ≤6 full, −1.5 per extra point |
| Tutor access | 20 | per non-commander piece, how many deck tutors can find it (2+ = full) |
| Redundancy | 10 | other complete combos sharing an outcome or a piece |
| Fragility | 15 | −4 graveyard-dependent, −2 per creature piece, −1 per artifact/enchantment piece |
| Outcome | 15 | `game_winning` or has a detected outlet = 15; otherwise 7 |

`game_winning` is true when a produced feature ends the game: winning or a loss for opponents, exiling all of opponents' permanents (e.g. Aminatou + Nicol Bolas, Dragon-God + Oath of Teferi), locks ("opponents can't cast/untap"), infinite turns, or infinite damage, life loss or mill aimed at opponents. Self-only effects don't count.

The weights are a proposed heuristic, not a standard. Present the score as a comparison aid between this deck's combos, and explain the main driver in words ("two cards, but both are 6-drops with no tutor for Triskelion").

## Bracket implications

- Brackets 1–2: no intentional two-card combos (Bracket 1 none at all).
- Bracket 3: no two-card combos before turn 6. The script flags `early_two_card` when both pieces cost ≤4 and total ≤8 MV. That's a rule of thumb; refine it with the deck's ramp and tutors and say it's a judgment.
- Bracket 4–5: anything goes.
Spellbook's `bracketTag` (enum verified against `/schema/`, Oct 2026): E Exhibition, C Core, O Oddball, P Powerful, S Spicy, R Ruthless, B Banned. It's shown per combo and, when the response has it, per deck (`estimate-bracket`). Combos whose features include **Mass Land Denial** are flagged (`mass_land_denial`). Both go to `bracket_floor.py` as **judgment input**, not as hard-floor changes. Spellbook's scale isn't the official 1–5 scale, so don't quote a tag as a bracket number. Do say when a Ruthless or MLD combo makes a low rules floor misleading.

## If Spellbook is unreachable

From a blocked sandbox, use the browser path. Open any **commanderspellbook.com** page; the backend refuses other origins with "Failed to fetch". Run `scripts/browser/combos_spellbook.js` there, either with `DECK_URL` set to the Moxfield/Archidekt link or after running the `window.DECK = …;` line from `python scripts/edh_common.py names-js deck.json`. Join the chunks with `python scripts/edh_common.py join spellbook.json part-*.txt` and run `find_combos.py --response spellbook.json`. The snippet also fetches `estimate-bracket`. Details are in `references/browser_fetch.md`.

If even that fails, the script exits with a clear message. Say plainly that combo detection couldn't run, then list combos you're confident about from your own knowledge, labelled as unverified ("from memory, not checked against Commander Spellbook"). Don't present a guess as a database result.

## Credit and etiquette

Spellbook asks for: a User-Agent naming your service (set by `edh_common`), ≤ ~80 requests/minute, handling 429s, never scraping the whole dataset through the API (use the bulk file), and **credit with a link to commanderspellbook.com** wherever results are shown. Keep the credit line `combos.md` ends with, and link each combo to its Spellbook page.

Details of the API, response fields and what's verified: `references/spellbook_api.md`.
