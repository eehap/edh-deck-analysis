---
name: edh-deck-structure
description: 'Structural assessment of a Magic: The Gathering Commander/EDH deck — tags every card''s role (ramp, card advantage, targeted and mass interaction, protection, tutors, recursion, win conditions, engine), compares counts with the Command Zone "New Era" template adjusted for strategy and bracket, and checks the mana base with Frank Karsten''s land-count formula and 99-card colored-source table (curve, pips, tapped lands, MDFCs). Use it whenever someone asks whether their Commander deck has enough ramp/draw/removal/lands, why it keeps flooding or getting color-screwed, how many lands or sources to run, or wants a deck "health check" — even without the word "structure". Needs deck.json from edh-deck-intake.'
---

# EDH deck structure

The goal is an honest picture of what the 99 actually do, measured against sensible targets, with every number traceable to a card. Scripts produce the counts; you supply the judgment the rules can't: what counts as "on plan" for *this* commander.

## Workflow

Run from this skill's folder (scripts are standard-library Python). Input is `deck.json` from edh-deck-intake.

1. **Tag roles.** `python scripts/tag_roles.py deck.json -o roles.json`
   Rules on oracle text plus Scryfall oracle tags (when the deck has them). Each card gets up to 3 roles at weights 1.0 / 0.5 / 0.25 with a confidence and a source. Flags ride along, among them `game_changer`, `mld`, `extra_turn`, `sac_outlet`, `symmetrical_wipe`, `pillow_fort`, `polymorph`, `reveal_until_creature`/`_or_pw` and `cheat_into_play`.
   The rules read ownership, because the tags often get this wrong:
   - Removal and wipes count only when they can hit an opponent's permanent. "Exile target creature you control, then reveal until a creature" (Mass Polymorph, Synthetic Destiny, Identity Echo) is a polymorph **engine**, not removal.
   - Ramp counts only mana *you* get from this card's own ability or spell. Granted abilities in quotes (Emrakul, the Exigent Doom) and an opponent's Treasure (Vraska, Betrayal's Sting) don't count.
   - Pillow fort (Propaganda, Ghostly Prison) is `protection`, and token makers get a `tokens` role (fodder).

   When a text rule contradicts an oracle tag, the rule wins, and `tag_vetoes` on the card says why.
2. **Review what the rules couldn't settle.** `roles.json["needs_review"]` lists cards where rules and tags disagree, only weak signals fired, or nothing fired. Decide each one by reading its oracle text against the commander's plan, then write `overrides.json`:
   ```json
   {"Viscera Seer": {"roles": {"engine": 1.0}, "note": "free sac outlet; fuels Meren's experience counters"},
    "Mikaeus, the Unhallowed": {"roles": {"engine": 1.0, "wincon": 1.0}, "note": "undying engine; combos with Triskelion"},
    "Darksteel Colossus": {"roles": {}, "note": "off-plan: never dies, so no Meren value"}}
   ```
   An override's `roles` replaces that card's roles (the land role is kept). `flags_add`/`flags_remove` adjust flags. Two more keys feed the mana analysis: `"cheated": true` marks a card the deck puts into play without casting (polymorph or reanimation hits, sneak targets), so its pips don't drive colour requirements; `"x_value": 5` sets the X an X spell is judged at. Pass the same file to `mana_analysis.py` and `structure_report.py`; role-dependent flags such as `symmetrical_wipe` are recomputed after overrides. Cite the text behind your call in `note`. That note becomes the reason shown to the user, and it keeps you honest. Use `engine` for cards whose value comes from the commander's theme; leave `roles` empty and write "off-plan" in the note for cards that do nothing for the deck, because the cut/add skill treats those as prime cuts. You may also correct a confident-but-wrong tag. Read `references/role_taxonomy.md` for edge cases (conditional ramp, cantrips, looting, symmetrical wipes, counterspells-as-protection).
3. **Pick a strategy profile**: `midrange` (default), `voltron`, `spellslinger`, `tokens`, `aristocrats`, `landfall`, `stax`, `combo`, `polymorph` (alias `cheat`), `reanimator`. Polymorph, cheat and reanimator expect fewer win conditions in hand, more engine and fodder, and tolerate many 7+ drops. They also auto-mark the big creatures as cheated when the deck has 3+ cheat effects; an override with `"cheated": false` keeps a card in the colour check. Choose from the commander and what the 99 are doing; if it's genuinely unclear, ask. Pass the user's bracket if known (1–5).
4. **Mana.** `python scripts/mana_analysis.py deck.json roles.json -o mana.json --strategy <profile> --overrides overrides.json [--bracket N]`
5. **Report.** `python scripts/structure_report.py deck.json roles.json mana.json --overrides overrides.json --strategy <profile> [--bracket N] -o structure.json --md structure.md`

## Reading the output well

- Counts are **weighted and overlapping** by design: the New Era template sums past 100 because Beast Within is removal and a cantrip creature is half a draw spell. Don't "fix" this by forcing a total of 100.
- **Lands**: show both Karsten's figure and the ~36 EDHREC average, and explain the gap rather than picking one silently. Karsten's formula is `31.42 + 3.13 × avgMV − 0.28 × cheap ramp/draw`; most real decks run fewer lands than it recommends, and most players under-build lands.
- **Colors**: the hardest card per color sets the requirement (a `{B}{B}` two-drop needs 30 black sources in 99 cards). When a single greedy card drives a big deficit, say so; "cut that one card" is often better advice than "rebuild the mana".
  - Cheated cards are excluded, and the report lists them. Don't blame a polymorph target's `{W}{W}{W}` for the mana.
  - X spells are judged at a realistic X: the printed threshold ("if X is 5 or more"), else X=3, or the override's `x_value`. Martial Coup is not a two-drop.
  - **4–5 colour decks** can't reach Karsten's ~30 sources for a cheap double pip. They get `hardest_to_cast`, a ranking by sources-to-requirement ratio, instead of "raise W by ~10". Present it that way: which cards are late-game cards, and which colours the lands should favour.
  - The always-tapped and conditionally-untapped lands are listed by name, so name them in the report.
- **Hit density**: for every reveal-until effect (Polymorph, Jace's −3, Identity Echo…) the report gives how many cards in the 99 it can hit (creature-only vs creature-or-planeswalker) and their average MV. In polymorph decks this is often the most useful number. Fewer hits means each effect digs deeper; a low average MV means weak hits.
- **Ramp** means permanent acceleration. Rituals aren't ramp. Sacrifice-for-mana altars are combo pieces that happen to make mana (weight 0.25).
- Targets are a starting point, not law. If a role is high because the strategy wants it (recursion in aristocrats, protection in voltron), say that instead of calling it a problem. The Command Zone made the same point in Ep. 659, "The Problem with Deckbuilding Templates".
- The colored-source table is reproducible: `python scripts/karsten_sim.py --cost 1CC` simulates Karsten's method (London mulligan with the free Commander mulligan, 41-land deck, conditioned on hitting land drops). `--verify` matches the published table to within one source. Use it when the user wants to see a number for their own land count (`--lands 36`).

## Without oracle tags

If `deck.json` has no oracle tags (API-only intake), everything still works but more cards land in `needs_review` and confidence is mostly "medium". Mention that the tagging was rules-only.

## Output

`structure.json` (role table with have/target/range/status, per-card roles with sources, flags, unassigned cards, full mana analysis) and `structure.md`, a ready-to-paste section for the report. edh-cut-add and edh-deck-review consume `structure.json`.

References: `references/role_taxonomy.md` (definitions, edge cases), `references/targets.md` (where the numbers come from, source conflicts, strategy shifts), `references/mana.md` (Karsten tables, fractional source rules, land quality).
