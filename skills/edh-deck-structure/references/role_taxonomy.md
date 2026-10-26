# Role taxonomy for automated tagging

A card may hold up to 3 roles at weight 1.0, 0.5 or 0.25. Rules and oracle tags agreeing gives high confidence; disagreement or a missing signal goes to model review, and the model must cite the oracle text behind its choice.

| Role | Definition | Primary signal | Edge cases |
|---|---|---|---|
| `land` | Land cards | type line | MDFC with a land back: 0.8 land (1.0 if mythic) plus its spell role |
| `ramp` | Permanent mana acceleration: rocks, dorks, land-to-battlefield, cost reducers | otags ramp/mana-rock/mana-dork; `{T}: Add` on nonlands; "search your library for … land … onto the battlefield" | Rituals are a `ritual` flag, not ramp. Tribal/conditional ramp 0.5. Treasure makers 0.5 if repeatable, 0.25 one-shot. Sac-for-mana altars 0.25 + `sac_outlet`. Land search to hand only = not ramp. Opponent's land search (Assassin's Trophy) = not ramp |
| `card_advantage` | Net card gain; flags `draw_engine` (repeatable) and `draw_burst` (one-shot) | otags draw/card-advantage; "draw two", "whenever … draw" | Cantrips 0.25. Impulse draw 0.5. Looting/rummaging is selection, not advantage. Wheels 0.5 (symmetrical) |
| `targeted_interaction` | Answers one threat: removal, counterspells, bounce, edicts | otags removal/counterspell; "destroy/exile target …", "counter target spell" | Bounce 0.5. Edicts 0.5 (opponent picks). Graveyard hate 0.5 (`graveyard_hate` flag) unless it hits all graveyards |
| `mass_interaction` | Board wipes, one-sided wipes, mass bounce | otags sweeper/board-wipe; "destroy all", "all creatures get -X/-X", "creatures your opponents control get" | Symmetrical wipes get a `symmetrical_wipe` flag; in tokens/voltron decks they're a liability, call it out. Stax pieces count here in stax decks |
| `protection` | Protects your board or commander | otags protection/gives-hexproof; "creatures you control gain hexproof/indestructible", "equipped creature has shroud" | A creature's own keyword (Darksteel Colossus's indestructible) is not the role. Counterspells: interaction 1.0 + protection 0.5 |
| `tutor` | Searches for a non-land card | otag tutor-*; "search your library for a … card" | Land tutors are ramp. Self-named searches (Rat Colony style) aren't tutors |
| `recursion` | Returns cards from the graveyard | otags recursion/reanimation | Casting itself from the graveyard (Gravecrawler) 0.25 |
| `wincon` | Ends the game or presents lethal | combo outcome "win"; otag win-condition; "you win the game"; overrun effects 0.5 | Mostly model judgment. Repeatable drain payoffs 0.25 by rule; raise when the deck can go infinite with them |
| `engine` | Plan cards that make the commander's strategy work | model judgment (+ EDHREC synergy when available) | Rules assign it only to polymorph / cheat-into-play effects (weight 1.0 / 0.5). Otherwise assign it in review, sparingly, with a reason |
| `tokens` | Makes creature tokens (fodder for polymorph, sacrifice, go-wide) | "create … creature token"; otag repeatable-creature-tokens | Repeatable (whenever / at the beginning / activated) 1.0, one-shot 0.5. Targets only exist in token-hungry profiles |
| flags | `stax`, `mld`, `extra_turn`, `game_changer`, `sac_outlet`, `pillow_fort`, `polymorph`, `reveal_until_creature`, `reveal_until_creature_or_pw`, `cheat_into_play`, `reanimation` | oracle text / Scryfall field | Bracket check; hit density; cheated-card suggestions |

## Ownership rules (the most common tagging errors)

- **Polymorph is engine, not removal.** "Exile target creature you control / exile all creatures you control … reveal until … put onto the battlefield" (Mass Polymorph, Synthetic Destiny, Identity Echo) is `engine` with the `polymorph` flag. If the target can also be an opponent's creature (Polymorph, Proteus Staff), add `targeted_interaction` 0.5, since the opponent gets a random replacement. Oracle tags often call these wipes or removal; the text rule vetoes them.
- **Removal and wipes need an opponent-reachable target.** "Exile target creature you control" (blink) isn't removal; "destroy all creatures you control" isn't a wipe.
- **Ramp is mana you produce.** It must come from this card's own ability or spell. Abilities granted in quotes ("target land gains '{T}: Add…'", Emrakul, the Exigent Doom) don't count, and neither do Treasures given to an opponent (Vraska, Betrayal's Sting's −2) or stolen lands. Tag-only ramp with no supporting text is dropped.
- **Pillow fort is protection.** Propaganda, Ghostly Prison and "creatures can't attack you" get `protection` and the `pillow_fort` flag.
- Each veto is recorded on the card as `tag_vetoes`, so you can see when the rules overruled a tag.

## How to review a flagged card

Ask, in order:
1. What does the text literally do? Quote the clause.
2. Does it do that reliably in this deck? (a conditional ramp piece whose condition the deck rarely meets is 0.25–0.5)
3. Is its value mainly from the commander's plan? Then `engine`.
4. Does it end games here, alone or with one other card in the deck? Then `wincon`.
5. Nothing? Empty roles and an "off-plan" note.

Avoid stacking roles to make a card look good. Three half-roles is usually a sign the card is a jack of all trades the deck could replace.

## Known rule-engine limits

Rules fail on modal spells, conditional text, cards whose text refers to other named mechanics, and engines that only matter with the commander. Expect 10–20% of a deck in review when oracle tags are present, more without them.
