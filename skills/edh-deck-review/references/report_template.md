# Report template

Keep these headings and this order. Fill every section; if a section has nothing to say, write one line saying so and why (e.g. "No complete combos found").

```markdown
# Deck review: <Commander(s)> [<color identity>]

**Brief:** Bracket <N> (<user-stated | assumed>), goal <tune | power up | budget | health check>, budget <$X/card | none>, protected: <cards | none>, collection: <none | prefer | only — N cards>.
**Data:** Scryfall <date> · oracle tags <yes/no> · Commander Spellbook <live | bulk | unavailable> · EDHREC <used | unavailable> · bracket rules verified through <date>.

## Verdict
3–5 lines: what the deck is trying to do, how well it's built to do it, bracket floor vs estimate,
and the two or three changes that matter most.

## Bracket
- Minimum by rules: **<N> (<name>)** — reasons as bullets (Game Changers listed, MLD, extra turns, two-card combos).
- Estimate (judgment): **<N>** — speed, fast mana, tutors, combo turn vs the bracket's turn expectations; the user's intent;
  Spellbook combo/deck tags and any combo that produces Mass Land Denial (from `judgment_inputs`).
- Conflicts with the target bracket, and what to change to fit.

## Structure
<role table from structure.md: Role | Have | Target | Range | Status>
Profile used: <profile>; counts are weighted and overlap.
2–4 bullets interpreting the table (what's genuinely short or long and why it matters for this commander).
Hit density (decks with reveal-until/polymorph effects): effect | can hit | eligible cards | avg MV of hits.

## Mana base
- Lands: <n> vs Karsten <x> vs EDHREC average ~36 — recommendation.
- Colors: hardest card per color, sources needed vs present (4–5 colours: the hardest-to-cast ranking instead).
  Name the cards excluded as cheated into play, and the X used for X spells.
- Tapped lands by name, conditional lands by name, land quality, curve (one line).
- Concrete fixes (e.g. "swap 3 Swamps for Overgrown Tomb, Woodland Cemetery, Llanowar Wastes").

## Combos
| Combo | Result | Game-winning | Spellbook tag | Robustness | Notes (outlet, fragility, MLD, bracket) |
One-card-away unlocks (card → combos it completes). Two-away highlights if requested.
_Combo data from Commander Spellbook (https://commanderspellbook.com)._

## Recommended changes
**Must change for the bracket** (if any).
| # | Cut | Add | Why (cut) → why (add) | Price (or "owned") |
With a collection: "N of M adds are already in your collection; the rest cost about $X." 
Priority order. 1–2 sentences of reasoning per swap, citing card text or deck numbers.
Optional: "Also consider cutting" and "If budget allows" lists.

## Notes and caveats
- Judgment calls made (on-plan/off-plan decisions that drove cuts).
- Degraded data and what it might have missed; data fetched via the browser path (say which sources).
- Rules still in beta / dates.

## Sources
Scryfall (card data, prices <date>), Commander Spellbook (combos), EDHREC (synergy, if used),
Wizards of the Coast Commander Brackets (<date>), Frank Karsten (mana math), The Command Zone Ep. 658 (role targets).
```
