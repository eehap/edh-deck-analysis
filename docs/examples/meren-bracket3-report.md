> Example output from the first version of the skills (2026-10-23), run on the synthetic Meren test deck in `dev/fixtures/`. Later changes (game-winning combo detection, collection support, polymorph handling) aren't reflected here.

# Deck review: Meren of Clan Nel Toth [BG]

**Brief:** Bracket 3 (user-stated), goal: tune and upgrade, budget $10/card, protected: none.
**Data:** Scryfall Oracle Cards + Oracle Tags exports supplied by the user · oracle tags yes · Commander Spellbook: saved find-my-combos response · EDHREC unavailable (sandbox) · bracket rules verified through 2026-10-23.

## Verdict
A well-built Golgari aristocrats deck: free sac outlets, death-trigger payoffs and plenty of recursion feed Meren every end step, and two real combos close games. It fits Bracket 3 by the rules and plays like a solid Bracket 3. The three changes that matter most: fix the black mana (the deck is well short of the sources its double-black spells want), trim the surplus ramp, and replace the handful of cards that do nothing with Meren (Darksteel Colossus first).

## Bracket
- **Minimum by rules: 3 (Upgraded)**
  - 3 Game Changers: Demonic Tutor, Worldly Tutor, Survival of the Fittest (Bracket 3 allows up to 3).
  - Two-card combo Mikaeus, the Unhallowed + Triskelion: both pieces cost 6, so it can't realistically come together before turn 6.
  - No mass land denial, no extra turns.
- **Estimate (judgment): 3.** The fastest kill is the 3-card Gravecrawler loop, which needs another Zombie and Gravecrawler in the graveyard; with 4 tutors it's assemblable but rarely before turn 6–7. That's in line with Bracket 3's 6+ turn expectation.
- **No conflicts with Bracket 3.** Adding a fourth Game Changer would push it to Bracket 4.

## Structure
| Role | Have | Target | Range | Status |
|---|---|---|---|---|
| Lands | 36.8 | 35.8 | 35–40 | OK |
| Ramp | 14 | 10 | 8–12 | HIGH |
| Card advantage | 10.25 | 12 | 9–14 | OK |
| Targeted interaction | 9 | 10 | 8–12 | OK |
| Mass interaction | 4 | 4 | 2–6 | OK |
| Protection | 3.5 | 4 | 2–8 | OK |
| Tutors | 4 | 2 | 0–4 | OK |
| Win conditions | 3.75 | 4 | 2–6 | OK |
| Recursion | 7 | 4 | 3–6 | HIGH |
| Engine / synergy | 8.5 | – | – | – |

Profile: aristocrats. Counts are weighted and overlap (Living Death is both a wipe and recursion).
- **Ramp is the real surplus.** 14 pieces against 8–12, and three of them are 4–5 mana rocks (Thran Dynamo, Gilded Lotus, Burnished Hart) in a deck whose curve tops out at 4.
- **Recursion runs high on purpose.** Meren is itself a recursion engine, so 7 is fine for aristocrats; trim only the clunkiest piece (Dread Return).
- **Card advantage is fine in practice.** The count reads 10.25, but Skullclamp, Grim Haruspex, Midnight Reaper and Harvester all draw repeatedly off deaths you're causing anyway.
- **Off-plan:** Darksteel Colossus never dies, so it never triggers Meren, Blood Artist or Pitiless Plunderer.

## Mana base
- **Lands:** 36.8 (Bala Ged Recovery counts as 0.8). Karsten's formula recommends **35.8** (avg MV 3.02, 18 cheap ramp/draw pieces); the EDHREC average is ~36. Land count is right; don't add more.
- **Colors** (rules, from Karsten's 99-card table):
  - **Black: short.** Sign in Blood ({B}{B} on turn 2) wants **30** black sources; the deck has **22.5** at that point (22 lands + Birds). 46 black pips against 28 green.
  - **Green: slightly short.** Eternal Witness ({1}{G}{G}) wants 28; the deck has 25.8.
- 5 lands always enter tapped (Golgari Rot Farm, Jungle Hollow, Bojuka Bog, Evolving Wilds, Bala Ged Sanctuary), plus 2 conditional. Average land quality 0.92. Curve: 1: 9 · 2: 19 · 3: 18 · 4: 8 · 5: 3 · 6: 4 · 7+: 2.
- **Fixes:**
  1. Replace Reliquary Tower with an untapped B/G dual. A colorless land in a deck this hungry for both colors costs you a source of each.
  2. Replace 2 Forests with B/G duals (slow lands or surveil lands are budget-friendly); each adds a black source without losing green.
  3. Consider swapping Sign in Blood for a {1}{B} or {2}{B} draw spell. It's the single card driving the 30-source requirement; at MV 3 a {B} single-pip card needs only 16.

## Combos
| Combo | Result | Robustness | Notes |
|---|---|---|---|
| [Mikaeus, the Unhallowed + Triskelion](https://commanderspellbook.com/combo/1234-5678/) | Infinite damage | 82/100 | Wins outright. Two pieces, both tutorable (Demonic Tutor, Diabolic Intent, Worldly Tutor, Survival), but 12 mana total and both die to creature removal. Not early enough to break Bracket 3 |
| [Gravecrawler + Phyrexian Altar + Blood Artist](https://commanderspellbook.com/combo/2345-6789/) | Infinite drain | 76/100 | Wins outright. Cheap (6 MV), but needs another Zombie on the battlefield (Mikaeus counts) and Gravecrawler in the graveyard; exposed to graveyard hate |

**One card away:** Nim Deathmantle completes Ashnod's Altar + Nim Deathmantle + Pitiless Plunderer (infinite death triggers and mana, with Blood Artist/Zulaport as the outlet). It's a 3-card combo, so it's fine for Bracket 3, and it's $3.

_Combo data from Commander Spellbook (https://commanderspellbook.com)._

## Recommended changes
| # | Cut | Add | Why | Price |
|---|---|---|---|---|
| 1 | Darksteel Colossus | Nim Deathmantle | Colossus can't die, so it does nothing for Meren or your death triggers. Deathmantle completes a third combo and doubles as recursion for any creature that dies. | $3.00 |
| 2 | Gilded Lotus | Fatal Push | Ramp is at 14 (range 8–12) and Lotus is the most expensive rock. Push is one-mana removal, and your sac outlets turn on revolt almost every turn. | $0.50 |
| 3 | Reliquary Tower | B/G untapped dual | Colorless land in a deck short on both colors; see Mana base fix 1. | varies |
| 4 | Forest | B/G dual | Adds a black source without losing green. | varies |
| 5 | Forest | B/G dual | Same; together with #3–4 this closes about 3 of the 7.5-source black gap. | varies |
| 6 | Thran Dynamo | Deadly Rollick | Second surplus 4-mana rock out; Rollick is free removal while Meren is out and exiles, which matters against recursive threats. | $0.50 |
| 7 | Dread Return | (your pick: a cheap card-draw engine) | Recursion is above range and Meren already reanimates every turn; a 4-mana sorcery-speed reanimation spell is the clunkiest copy. | – |

Also consider: **Pelakka Wurm** (7 mana; Meren can rebuy it, but a 3–4 mana death-trigger creature does more) and **Burnished Hart** (third surplus ramp piece).

Kept on purpose: **Living Death** (flagged as surplus recursion, but it's a one-sided reset in a graveyard deck) and **Massacre Wurm** (6 mana, but a one-sided wipe plus a drain engine).

## Notes and caveats
- Judgment calls: Viscera Seer, Gravecrawler, both altars, Blood Artist, Zulaport Cutthroat, Grave Pact and Mikaeus were classified as engine pieces (rules couldn't tag them); Darksteel Colossus as off-plan. These drove the cut list.
- EDHREC was unreachable, so the add pool came from Commander Spellbook and my own knowledge; synergy data didn't inform these picks. The B/G dual prices weren't checked; most slow lands and surveil lands are well under $10.
- Bracket rules are still labelled beta; the list and rules were verified through 2026-10-23.

## Sources
Scryfall (card data and prices, user-supplied export) · Commander Spellbook (combos) · Wizards of the Coast, Commander Brackets (rules 2025-10-21; Game Changers 2026-02-09) · Frank Karsten, colored-source table (2022) and land-count formula · The Command Zone Ep. 658 (role targets).
