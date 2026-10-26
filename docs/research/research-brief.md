# Research brief: data and methods for a Commander (EDH) deck-analysis skillset

## Goal
I am building a set of AI agent skills that analyze a Magic: The Gathering Commander deck and produce: (1) a structural assessment, (2) the combos it contains or nearly contains, and (3) a prioritized list of cards to cut and cards to add, each with a reason. The skills are:
1. Deck intake: parse a decklist and enrich every card with card data
2. Structure analysis: role tagging, role-count targets, mana curve, mana base health
3. Combo detection: complete and near-complete combos, and how robust they are
4. Cut/add recommender: score existing cards, find candidates, pair swaps
5. Orchestrator: run the above and write a consistent report

Research what is needed to build each one. Prioritize current, primary sources (official APIs and docs, Wizards of the Coast announcements, the tool maintainers' own pages). Information must be current as of October 2026; flag anything that may be outdated, and note the date of each source.

## Research questions

### A. Decklist intake
- What export formats do Moxfield, Archidekt, MTGO, MTG Arena and plain-text lists use? Give a concrete example of each, including how they mark the commander, companion, sideboard/maybeboard, set codes, collector numbers and foil markers.
- Do Moxfield and Archidekt offer public APIs or stable JSON endpoints for fetching a deck by URL? What are their terms of use and rate limits?
- How should names be normalized for double-faced cards, split cards, adventures, flip cards, Alchemy/digital-only cards and Universes Beyond printings?

### B. Card data (Scryfall)
- Scryfall API: relevant endpoints (named lookup, /cards/collection batch lookup, search), the bulk data files (which file to use, size, update frequency), rate limits and attribution requirements.
- Which fields matter for this analysis (oracle_text, mana_cost, cmc, color_identity, type_line, keywords, legalities.commander, produced_mana, card_faces, prices, game_changer, edhrec_rank), and how are multi-faced cards represented?
- Scryfall Tagger "oracle tags" (otag:): what they are, whether they are queryable through the API, and how usable they are for automatically tagging card roles (ramp, removal, draw, tutor, etc.).

### C. Role taxonomy and structural targets
- What established frameworks exist for Commander deck composition? Cover at least: the Command Zone deckbuilding template (and any updated versions), EDHREC's average-deck data, and other widely cited templates. Give the recommended counts for lands, ramp, card draw, targeted removal, board wipes, protection and win conditions, and how they differ between sources.
- How do these targets shift by deck strategy (e.g. voltron, spellslinger, tokens, aristocrats, landfall, stax, combo) and by power level/bracket?
- Propose a role taxonomy suitable for automated tagging: role names, definitions, edge cases (cards that fill multiple roles, conditional ramp, card-advantage engines vs one-shot draw), and how to resolve ambiguity.
- Can roles be assigned reliably from oracle text with rules or patterns, from Scryfall otags, or does it need model judgment? What has worked in existing tools?

### D. Mana base analysis
- Frank Karsten's research on colored sources: the numbers adapted for 99-card singleton Commander decks, and the method behind them (hypergeometric targets) so the calculation can be reproduced in a script.
- Recommended land counts by average mana value and ramp count; how to count MDFCs, cheap mana rocks and cycling lands toward the land count.
- How to evaluate land quality (tapped vs untapped, fetches, utility lands) and color requirements from pip counts.

### E. Combo detection (Commander Spellbook)
- Commander Spellbook's API: endpoints (especially the "find my combos" / estimate-bracket endpoints that accept a decklist), request and response schema with an example, rate limits and terms of use.
- How it reports complete combos versus combos missing one or more cards, and what metadata it returns (prerequisites, steps, results, mana needed, color identity, popularity).
- How to judge combo quality and robustness: number of pieces, total mana, tutor availability in the deck, vulnerability to common removal and graveyard hate, and whether it wins outright or needs another outlet.

### F. Brackets and power level
- The current official Commander bracket system: definitions of each bracket, the current Game Changers list, and the rules on tutors, mass land denial, extra turns and two-card combos. Note the date of the most recent update.
- How Commander Spellbook and others estimate a deck's bracket, and whether that is available programmatically.

### G. Cut/add candidates and card evaluation
- EDHREC: what data it exposes per commander (top cards, synergy scores, inclusion percentages, themes, average decks, salt scores), whether stable JSON endpoints exist, and the terms of use for automated access.
- What a "synergy score" measures and its known weaknesses (popularity bias, new cards).
- Heuristics experienced players use to choose cuts: mana efficiency, redundancy within a role, off-plan cards, high-cost low-impact cards, "win-more" cards. Find written sources (articles, podcasts with show notes) that articulate these.
- How to filter candidates by color identity, legality, budget (price sources and their reliability) and the user's target bracket.
- How to pair a cut with an add so that role counts move toward targets.

### H. Prior art
- Existing open-source projects, scripts or tools that analyze Commander decks (role tagging, mana analysis, combo finding, recommendations). For each: what it does, language, license, whether its data or logic is reusable, and lessons learned.

## Deliverable
A structured report with one section per letter above. For each section:
- Findings stated concisely, with citations (title + URL) for every factual claim
- For APIs: endpoint URLs, an example request and an abbreviated example response, rate limits, terms of use
- Concrete numbers and tables where relevant (role targets, colored-source tables)
- A short "implications for the skill" paragraph: what the skill should do, which data source to use, and what to watch out for
- Open questions or conflicts between sources, explicitly flagged

End with: (1) a recommended role taxonomy, (2) a recommended default set of role-count targets with ranges, and (3) a list of risks: data access restrictions, staleness, licensing, and anything that needs model judgment rather than rules.