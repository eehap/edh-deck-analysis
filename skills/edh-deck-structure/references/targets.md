# Role-count targets: sources, conflicts, strategy shifts

## Established templates

| Category | Command Zone original (Ep. 379) | Command Zone "New Era" (Ep. 658, Feb 18 2025) | 2026 guides (Kraken the Meta, Spellweave) |
|---|---|---|---|
| Lands | 35–38 | 38 | 36–38 |
| Ramp | 10 | 10–12 (10 baseline) | 8–12 / 10–12 |
| Card advantage | 10 | 12 | 8–12 |
| Targeted removal / disruption | 5 | 12 | 8–10 |
| Board wipes / mass disruption | 5 | 6 | 2–4 |
| Plan | 25 standalone + 10–12 enhancers + 7–8 enablers | ~30 (overlap allowed) | 25–30 |
| Protection / win cons | not separate | folded into Plan | win cons 2–4 (Spellweave) |

EDHREC average land count: about 36 (range 33–38) per CoolStuffInc's "How many Lands do you need in a Commander deck?" (Apr 27 2026).

### Conflicts to flag rather than hide
1. New Era totals exceed 100 because cards count in several categories. One transcription forces "~22 plan" to reach 100; don't.
2. An intermediate edh.fandom version says wipes 3–4 and removal 10–12; Ep. 658 says 6 mass disruption. That's a version difference, not an error.
3. Ep. 658 counts ramp as permanent acceleration only. No rituals.
4. Ep. 659, "The Problem with Deckbuilding Templates", discusses when to deviate. Deviations that serve the strategy are fine.

## Defaults used (Bracket 2–3 midrange) — `scripts/targets.json`

| Role | Target | Range | Basis |
|---|---|---|---|
| Lands | Karsten formula (usually 37–38) | 35–40 | Karsten 2022; Ep. 658 |
| Ramp | 10 | 8–12 | Ep. 658 |
| Card advantage | 12 | 9–14 | Ep. 658 |
| Targeted interaction | 10 | 8–12 | between Ep. 658 (12) and 2026 guides (8–10) |
| Mass interaction | 4 | 2–6 | spans guides and Ep. 658 |
| Protection | 4 | 2–8 | synthesis |
| Tutors | 2 | 0–4 | synthesis; no bracket tutor cap since Oct 2025 |
| Win conditions | 4 | 2–6 | Spellweave 2026, widened |
| Recursion | 3 | 0–6 | synthesis |

## Strategy shifts (synthesis of common practice; heuristics, not a primary source)

| Strategy | Adjustments |
|---|---|
| Voltron | Protection 6–10; wipes 0–3; cheap equipment counts as plan |
| Spellslinger | Lands 33–36 with many cantrips; more draw; cheap interaction doubles as plan |
| Tokens | ≤2 symmetrical wipes; anthems/finishers are win conditions |
| Aristocrats | Sac outlets are engine; recursion 3–6 |
| Landfall | Lands 40–44+; land ramp overlaps with plan |
| Stax | Ramp is asymmetric; stax pieces count as mass disruption; MLD means Bracket 4+ |
| Combo | Tutors 4–10; more protection/counters; 34–36 lands with fast mana |
| Polymorph / cheat | Win cons 1–4 (the library hands you threats); engine 7–20; token fodder 4–12; up to 16 cards at 7+ MV is fine because they're cheated in. Report hit density; big hits are excluded from colour requirements |
| Reanimator | Recursion 5–14; engine (self-mill/discard enablers) 5–16; up to 14 cards at 7+ |

Brackets: lower brackets favour more lands and slower interaction; Bracket 4–5 decks run lower curves, fast mana and more tutors. The official turn expectations (B1 9+ turns down to B4 4+) quantify that. For cEDH, generic targets fit poorly; judge against the competitive meta.

When you use a profile, say which one in the report, and if you deviate from it for a reason, say why.
