# Mana base: Karsten's numbers and how they're applied

## Colored sources for 99-card decks
Frank Karsten, "How Many Sources Do You Need to Consistently Cast Your Spells? A 2022 Update" (ChannelFireball, now TCGplayer; exact 2022 date unconfirmed). "Consistently" = 90% for one-drops, 91% on the play for two-drops, and so on, given you hit your land drops.

| Cost | Sources | Cost | Sources |
|---|---|---|---|
| C | 19 | 5C | 14 |
| 1C | 19 | 4C | 15 |
| 2C | 18 | 3C | 16 |
| CC | 30 | 5CC | 20 |
| 1CC | 28 | 4CC | 22 |
| 2CC | 26 | 3CC | 23 |
| CCC | 36 | 4CCC | 26 |
| 1CCC | 33 | 3CCC | 28 |
| CCCC | 39 | 2CCC | 30 |
| 1CCCC | 36 | | |

Method (reproduced by `scripts/karsten_sim.py`): ≥(89+M)% chance of N colored sources by turn M on the play, conditional on ≥M lands; 41-land deck; free mulligan + Commander turn-1 draw; London mulligan (mull the free 7 with 0,1,2,6,7 lands; later 7s with 0,1,6,7; 6-card hands with 0,1,5,6; bottom toward ~3 lands, off-color lands first). Hypergeometric core: X ~ Hypergeom(99, K, 7+M). The simulation's `--verify` matches 6 of 8 published cells exactly and the rest within one source.

Applying it: the most demanding card per color sets the requirement. Generic part = MV minus that color's pips; costs beyond the table's generic range use the last column. Gold cards: +1 to each color's requirement (and check the combined count). Hybrid/Phyrexian pips count for each color they can pay. The commander's own cost is included.

## Counting fractional sources (Karsten 2022)
- Fetchlands: full source for each color they can fetch. Fabled Passage/Evolving Wilds-style: full in two-color decks, ~⅔ in 3+.
- Duals: full for each color. Only untapped lands count for turn-1 requirements.
- Mana rocks: ¾ per color, only for spells with MV ≥ 3. Dorks: ½, only for MV ≥ 2.
- 2-MV land ramp (Farseek, Rampant Growth): ¾ for MV ≥ 3. Cultivate-style 3-MV: counts only for MV ≥ 4, about ½ (the script uses ½ from MV 4).
- Treasure: ¼ each (not counted by the script). Exotic Orchard ¾ any color (full when opponents' colors are known). Fellwar Stone ½.
- MDFC land faces: 0.8 (non-mythic), 1.0 (mythic).

## Land count
Karsten, "How Many Lands Do You Need in Your Deck? An Updated Analysis" (TCGplayer):
**lands = 31.42 + 3.13 × avgMV − 0.28 × cheap ramp/draw**, derived as 99/60 × (19.59 + 1.90 × avgMV + 0.27) − 1.35 (the 1.35 for free mulligan + draw is a back-of-the-envelope estimate). avgMV is over nonland cards (MDFC by front face).

| Avg MV | Cheap ramp/draw | Lands |
|---|---|---|
| 2.5 | 15 | 35.0 |
| 3.0 | 12 | 37.4 |
| 3.5 | 10 | 39.6 |
| 4.0 | 8 | 41.7 |

"Cheap" isn't pinned down in the sources; FreeMully used MV ≤ 3 (a simulated Trostani deck at avgMV 3.51 with 13 cheap pieces bottomed out at 38.8 lands). The script defaults to ≤3; `--cheap-mv 2` is stricter and recommends more lands. Old rule of thumb: 40 lands minus 1 per 2 mana rocks — roughly consistent.

Conflict to show the user: Karsten usually lands at 37–40; EDHREC's real-world average is ~36. Most players under-build lands.

## Adjustments to the colour check
- **X spells** are judged at a realistic X, not their printed MV: the threshold printed on the card ("if X is 5 or more" → X=5), otherwise X=3, or `x_value` from overrides. Martial Coup {X}{W}{W} is judged as a 7-drop, not a two-drop.
- **Cheated cards** (put into play without casting: polymorph or reveal-until hits, reanimation targets, sneak-in targets) are excluded from colour requirements. They are auto-suggested when the deck has 3+ cheat effects (creatures at MV 6+, or MV 5 with a triple pip; planeswalkers at MV 6+ if an effect can hit them). They are applied automatically under the polymorph/cheat/reanimator profiles; elsewhere, mark them `"cheated": true` in overrides.
- **4–5 colour decks** can't reach the ~30 sources a cheap double pip needs. They get a ranking of the hardest cards to cast on curve (by sources ÷ requirement) instead of a per-colour "raise by N" target.

## Land quality (heuristic, not from a primary source)
Untapped dual/fetch 1.0 · conditional untapped (check/fast/slow/shock) 0.8 · tapped dual/tri 0.6 (0.75 with cycling/scry) · colorless utility 0.5 · basic 1.0.
Warnings: >6 always-tapped lands at Bracket 3+; any color below its requirement; colorless-only lands >10% of lands in 3+ color decks. Cycling lands count as full lands; cheap rocks count toward the formula's ramp term, not as lands.
