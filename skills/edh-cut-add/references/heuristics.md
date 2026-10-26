# Cut/add heuristics

Written sources for cut heuristics are thin; this list is a synthesis. Template and its deviations: Command Zone Ep. 658 and Ep. 659.

## Choosing cuts
1. **Role surplus.** Cut from roles above their target range first. Within the role, cut the most expensive copy that does the same job (a 4-MV rock when 2-MV rocks fill the slot).
2. **Mana efficiency.** Among cards with the same effect, keep the cheaper one; a card well above the median MV of its role is suspect.
3. **Off-plan.** Matches no commander theme or tag cluster and has low synergy. Confirm by reading the commander: does this card ever interact with it?
4. **High cost, low impact.** MV ≥ 6 without a game-winning or game-swinging effect (one-sided wipes and big engines are swinging; a vanilla 7/7 is not).
5. **Win-more.** Only matters when already ahead (anthems without a go-wide base, extra combat when you can't connect).
6. **Conditional cards** whose condition the deck rarely meets.
7. **Bracket violations.** Game Changers beyond the cap, MLD in Bracket ≤3, chainable extra turns in Bracket ≤3, two-card combos (none in B1, no intentional ones in B2, none before turn 6 in B3).

Weigh **all** roles: a card in a surplus role that also fills a role at or below target isn't a surplus cut. Never cut an **engine** card or a **cheated** card (put into play without casting) for role surplus or mana cost. In a polymorph deck, Agent of Treachery is a hit, not an overcosted removal spell.

Protect: the commander's core enablers, combo pieces the user wants, format staples with no real cost, and anything the user named.

## Finding adds
- EDHREC commander page (if reachable): high-synergy and high-inclusion cards not in the deck.
- Scryfall: `otag:<role> id<=<identity> legal:commander -is:digital [usd<=X] [-is:gamechanger]`, `order=edhrec`.
- Spellbook `almostIncluded`: single cards that complete combos, only if the bracket allows.
- Your own knowledge: archetype staples and commander-specific tech, especially cards newer than EDHREC's data window.
- The user's collection (optional): owned cards that fit the deck. Prefer mode adds +2 to owned cards (a tie-breaker the size of one below-target role); only mode removes everything else. Ownership is never a reason by itself; the add must still close a gap, add synergy or complete a combo.

## Pairing
Swap score = cut score + add score − 0.5 × max(0, add MV − cut MV). Greedy: the most over-target role gives the cut, the most under-target role receives an add of similar or lower MV. Recompute role totals after each swap. Keep land count and curve neutral unless the mana analysis says otherwise; then convert some cuts into lands.

## Filters
- Color identity (`id<=`), `legal:commander`, Game Changer cap for the bracket.
- Budget: Scryfall `prices.usd` (TCGplayer; EUR from Cardmarket; TIX from Cardhoarder), refreshed once a day. Label as an estimate with a date.

## Writing the reason
Bad: "Fatal Push is a strong removal spell."
Good: "You run 9 targeted answers against a target of 10, and most cost 3+. Fatal Push answers early threats for one mana, and Meren's sacrifice loop turns on revolt almost every turn."
