You are improving a set of five Claude skills for reviewing Magic: The Gathering Commander decks:
edh-deck-intake, edh-deck-structure, edh-combo-finder, edh-cut-add and the orchestrator edh-deck-review
(scripts/pipeline.py). Fix the problems below, keep the scripts standard-library Python, update each
SKILL.md to match, and verify with the acceptance test at the end.

## Context: what went wrong in a real run
The sandbox's shell could not reach api.scryfall.com, api2.moxfield.com, backend.commanderspellbook.com
or json.edhrec.com (proxy 403). The run only worked because the agent fetched data through a browser
pane with in-page fetch() and then retyped ~50 KB of JSON into files by hand. EDHREC was never reached,
so candidates.py returned 0 candidates and score_swaps.py produced no adds.

## 1. A supported browser-fetch path for blocked networks
- In each skill's SKILL.md "no network" section, document a browser fallback: open the site's own
  origin in a browser tab and run fetch() from the page. Observed CORS behaviour:
  - Scryfall API works from any origin (e.g. POST /cards/collection, 75 identifiers per call, 2 req/s).
  - Moxfield api2.moxfield.com/v3/decks/all/<id> works from a moxfield.com page.
  - Commander Spellbook find-my-combos works from a commanderspellbook.com page, not from other origins.
  - EDHREC: test json.edhrec.com/pages/commanders/<slug>.json from an edhrec.com page and document the result.
- Ship ready-to-paste JS snippets (in references/browser_fetch.md) that return EXACTLY the slim JSON each
  script accepts, so nothing has to be reshaped by hand: deck → parsed.json, cards → --cards-json,
  combos → --response, EDHREC → the new --edhrec-json below.
- Make those payloads small. Define a slim card schema (oracle_id, name, layout, mana_cost, cmc,
  type_line, oracle_text, color_identity, produced_mana, legalities.commander, game_changer, prices.usd,
  card_faces[name, mana_cost, type_line, oracle_text]) and make enrich.py accept it. Snippets should
  return results in chunks of ~25 KB because tool outputs get truncated.

## 2. Offline inputs everywhere a script calls the network
- pipeline.py phase1: if --deck is a URL and fetch fails, stop with a clear message suggesting the
  browser snippet or a pasted export; add --parsed-json to skip fetching entirely. Do not call
  `scryfall_data.py update` when --cards-json is supplied (it currently runs anyway and prints an error).
- candidates.py: add --edhrec-json (saved commander page) and --candidates-json (Scryfall-shaped cards
  the model or a snippet supplies). With neither, print the exact role gaps and a Scryfall query per gap
  (e.g. `id<=WUBR t:creature cmc>=6`) so the model can fetch candidates itself.
- pipeline.py phase2: pass these through.

## 3. Role tagging errors (tag_roles.py), seen on Jace, Multiverse Architect
- Self-targeting "exile your creatures / creature you control, reveal until creature, put onto
  battlefield" (Mass Polymorph, Synthetic Destiny, Identity Echo, Proteus Staff on your own token) was
  tagged board wipe or targeted removal. Tag these as engine (polymorph) and only count removal when the
  target can be an opponent's permanent.
- Emrakul, the Exigent Doom was tagged ramp because of a granted mana ability; Vraska, Betrayal's Sting
  was tagged ramp because its −2 makes the OPPONENT's creature a Treasure. Only count mana you produce
  for yourself from the card's own permanent or spell.
- Pillow fort (Propaganda, Ghostly Prison) and repeatable token makers (Bitterblossom, Skrelv's Hive)
  got no role at all. Tag fort as protection; tag token generation so profiles that use fodder can see it.
- The "symmetrical wipe" flag in structure_report.py ignores overrides.json; apply overrides first.

## 4. Mana analysis (mana_analysis.py / karsten logic)
- X spells are judged at their printed mana value (Martial Coup {X}{W}{W} treated as a turn-2 card).
  Judge them at a sensible X (default: the turn they are usually cast, e.g. X≥5 for wipe modes) or exclude.
- Cards the deck mainly puts into play without casting must not drive colour requirements. Add a
  "cheated" flag (settable in overrides.json, and auto-suggested when the deck has 3+ polymorph,
  reanimation or cheat-into-play effects) so their pips are excluded from the hardest-card check.
  In the real run, the report wrongly blamed Serra's Emissary (WWW) and Avacyn (BBB), which were
  polymorph targets.
- Four- and five-colour decks can never hit Karsten's ~30 sources for a cheap double pip. Report the
  shortfall as a ranking of hardest-to-cast cards, not as "raise W sources by ~10".
- List which lands were counted as tapped and conditional so the report can name them.

## 5. Strategy profiles and a new metric
- Add a `polymorph` (or `cheat`) profile to targets.json: fewer win conditions needed in hand, more
  engine and fodder expected, tolerance for a high 7+ count.
- For decks with reveal-until effects, report HIT DENSITY: number of eligible cards for each effect
  (creature-only vs creature-or-planeswalker), and their average mana value. That was the most useful
  number in the real review and had to be counted by hand.

## 6. Swap scoring (score_swaps.py)
- It suggested cutting Agent of Treachery, Ashen Rider and Marang River Regent because targeted
  interaction was "over range". Those cards were also polymorph targets. Don't flag a card for a role
  surplus when it fills another role or is marked engine/cheated; weigh all its roles.
- Never recommend cutting a cheated card for castability reasons.

## 7. Combo finder (find_combos.py)
- "Exile all of your opponents' permanents and hands" scored wins_outright=false. Treat exile-all /
  lock / "each opponent loses" features as game-winning.
- Surface Spellbook's bracketTag and a "Mass Land Denial" produced feature in the report and pass them
  to bracket_floor.py, which should mention them as judgment input (not a hard floor change).

## Acceptance test
Use this deck: https://moxfield.com/decks/nyDCfWMmHUKXdqfjC3Sv7w (commander Jace, Multiverse Architect,
WUBR, 100 cards, includes 2026 cards from sets "frc"/"fra"). If the network is blocked, use the browser
snippets. Expected after your changes:
- intake resolves 93 unique cards with 0 unresolved, without manual JSON retyping;
- Mass Polymorph, Synthetic Destiny, Identity Echo are engine, not wipes/removal; Emrakul and Vraska are
  not ramp; Propaganda/Ghostly Prison are protection;
- with --strategy polymorph, the mana report does not cite Serra's Emissary or Avacyn as hardest cards,
  and lists hit density (11 creature hits; 17 creature-or-planeswalker hits);
- candidates.py returns candidates from at least one source (EDHREC or Scryfall) or prints actionable
  per-gap queries;
- the Aminatou + Nicol Bolas + Oath of Teferi combo is marked game-winning.
Report what you changed per file and any item you could not complete.