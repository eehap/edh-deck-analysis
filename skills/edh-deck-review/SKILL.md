---
name: edh-deck-review
description: 'Full analysis of a Magic: The Gathering Commander/EDH deck in one consistent report — decklist intake, role and mana-base structure, combos (complete and near-complete, with robustness), bracket check against the official Commander Brackets and Game Changers list, and a prioritized cut/add list with reasons. Use this whenever someone shares a Commander decklist or deck link and asks for a review, a rating, feedback, "what''s wrong with my deck", "what bracket is this", upgrade advice or a deck doctor session, even if they only paste the list with a one-line question. It runs edh-deck-intake, edh-deck-structure, edh-combo-finder and edh-cut-add in order; for a narrow question (only combos, only mana) use that skill directly.'
---

# EDH deck review (orchestrator)

Run the four EDH skills in order and turn their outputs into one report a player can act on. Being consistent is the point: the same sections, in the same order, every number traceable, rules-based facts kept separate from judgment calls.

## 0. Settle the brief

From the conversation, or one short question if missing:
- **Target bracket** (1–5), or "tell me what it is".
- **Goal**: tune within the bracket, power up, budget-fix, or just a health check.
- **Budget** per card, if upgrades are wanted.
- **Untouchables**: cards they won't cut.
- **Collection** (optional): if they share one (a CSV export or a list), pass `--collection` to phase2. Ask once whether adds should come only from it (`--collection-mode only`) or just favour it (`prefer`, the default). edh-cut-add SKILL.md covers formats and the blocked-network path.
If the user isn't around to answer, assume: bracket = the rules floor computed below, goal = tune, no budget cap, nothing protected. State those assumptions at the top of the report.

## 1. Run the pipeline

The sibling skills must be installed next to this one (same parent folder). `scripts/pipeline.py` finds them and runs each script, printing every command so any step can be rerun by hand.

```
python scripts/pipeline.py phase1 --deck deck.txt|<url> --work work/ [--commander "Name"]
```
→ parse, resolve against Scryfall, tag roles, find combos. Then:

- Fix intake problems first (unresolved names, missing commander, deck size), as edh-deck-intake describes.
- Review `work/roles.json["needs_review"]` and write `work/overrides.json`, as edh-deck-structure describes. This is where you decide what is engine, what wins, and what is off-plan for this commander. Do it carefully; the cut list inherits these calls.
- In decks built around polymorph, reveal-until or reanimation, mark the big hits `"cheated": true` in overrides (or use the `polymorph`/`reanimator` profile, which suggests them), so their pips don't distort the mana verdict.
- Choose a strategy profile (midrange, voltron, spellslinger, tokens, aristocrats, landfall, stax, combo, polymorph/cheat, reanimator).

```
python scripts/pipeline.py phase2 --work work/ --strategy <profile> --bracket N [--budget USD] [--protect "Card"] [--max-swaps 10] [--extra-candidates names.json] [--collection my_collection.csv [--collection-mode prefer|only]]
```
→ mana analysis, structure report, bracket floor, candidates, swaps.

If a sibling skill can't be found, load it with the Skill tool to learn its path, then pass `--skills-dir`.

### Blocked network (sandbox proxy 403)

If the scripts print `Cannot reach … allowlisted`, or curl shows `CONNECT tunnel failed, response 403`, the shell can't reach the data sites. Don't keep retrying from the shell. If a browser tool is available, fetch everything with the snippets and pass the saved files. The full guide is `references/browser_fetch.md`, with tested CORS behaviour per site; snippet paths are relative to each sibling skill.

| Step | Where to run it | Snippet | Pipeline flag |
|---|---|---|---|
| Deck | the deck's moxfield.com page | `edh-deck-intake/scripts/browser/moxfield_deck.js` | phase1 `--parsed-json` (a pasted list → `--deck deck.txt` instead) |
| Cards + oracle tags | same tab (any origin works) | `edh-deck-intake/scripts/browser/cards_scryfall.js` | phase1 `--cards-json` (skips the Scryfall bulk update) |
| Combos | a commanderspellbook.com page (other origins are refused) | `edh-combo-finder/scripts/browser/combos_spellbook.js` | phase1 `--spellbook-response` |
| EDHREC | any tab (edhrec.com preferred) | `edh-cut-add/scripts/browser/edhrec_candidates.js` | phase2 `--edhrec-json` |
| Per-gap cards | any tab | `edh-cut-add/scripts/browser/scryfall_search.js` (after the printed `window.QUERIES` line) | phase2 `--candidates-json` |
| Collection card data (optional) | any tab, after the `window.COLLECTION` lines from `edh-cut-add/scripts/collection.py to-js` | `edh-cut-add/scripts/browser/collection_cards.js` | phase2 `--collection-cards` (with `--collection`) |

Each snippet returns `chunks=N`. Evaluate `window.__edh[0]` … `[N-1]`, save each result verbatim to `part-N.txt`, then run `python <intake>/scripts/edh_common.py join out.json part-*.txt`. Add `--offline` to phase2 so it doesn't attempt live calls. Never retype JSON by hand. With no browser either, follow each sibling skill's degraded path, and record in the report what was degraded.

## 2. Judge what the scripts can't

- **Combos:** confirm outlets and prerequisites (edh-combo-finder SKILL.md).
- **Bracket:** `bracket.json` gives the *minimum bracket by rules* with reasons, plus `judgment_inputs`: Spellbook's combo tags (Exhibition … Ruthless), its deck-level tag, and combos that produce Mass Land Denial. These don't move the floor, but they belong in your estimate. A deck with a rules floor of 1 and a Ruthless MLD-producing combo does not play at Bracket 1; say so. Then make your own *estimate* of where the deck plays: speed (fast mana, tutor density, combo assembly turn) against the official turn expectations (B1 9+, B2 8+, B3 6+, B4 4+ turns) and the user's intent. Keep the two clearly labelled. Wizards stresses intent and pregame conversation, so the estimate is advice, not a ruling.
- **Swaps:** veto and rewrite as edh-cut-add describes. The final list is yours.

## 3. Write the report

Use the template in `references/report_template.md`: same headings, same order, every time. Rules of thumb:
- Lead with a 3–5 line verdict: what the deck does, its bracket (floor and estimate), the two or three changes that matter most.
- Tables for role counts, combos and swaps; prose for reasoning.
- Every claim about the deck points to cards or numbers. "Low on interaction" becomes "9 targeted answers (target 10); 6 of them cost 3+".
- Separate **rules** (Game Changer count, Karsten math, combo pieces) from **judgment** (on-plan, win-more, bracket estimate), and say which is which.
- Name the profile and bracket the targets assumed, and any degraded data (no oracle tags, no EDHREC, model-sourced card data, combo lookup failed).
- End with sources and dates: Scryfall data date, Commander Spellbook credit and link (required by Spellbook), EDHREC if used (attribute it), bracket rules "verified through" date.

Deliver the report as the document format the environment offers (a document artifact if available; otherwise a Markdown file), and give a short summary in chat: verdict plus top swaps.

## Keeping it current

Bracket rules and the Game Changers list are dated in `scripts/bracket_rules.json` (rules last changed 2025-10-21, list last changed 2026-02-09, verified through 2026-10-23; the system is still labelled beta). If the current date is well past that, or the user mentions a new announcement, check Wizards' latest Commander update before relying on them, and update the file. Scryfall's `game_changer` field is authoritative over the bundled list. `references/brackets.md` has the rules in prose; `references/data_sources.md` lists data-access, staleness and licensing risks.
