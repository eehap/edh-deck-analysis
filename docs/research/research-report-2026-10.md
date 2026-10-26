# Commander (EDH) Deck-Analysis Skillset: Data Sources, Methods and Targets (October 2026)

You can build all five skills on two free, documented data sources: Scryfall for card data and Tagger oracle tags, and Commander Spellbook for combo detection and bracket hints. EDHREC, Moxfield and Archidekt should be treated as optional inputs that can break at any time. None of those three publishes an official API, so every integration with them relies on undocumented JSON endpoints.

## TL;DR
- **Data stack:** Scryfall is the card-data backbone. Download the Oracle Cards bulk file plus the Oracle Tags bulk file and join them on `oracle_id`. Scryfall's search, named and collection endpoints are hard-capped at 2 requests/second. Commander Spellbook's `POST /find-my-combos` returns complete combos (`included`) and one-card-away combos (`almostIncluded`) with mana, identity, bracket tag and popularity. Spellbook asks for no more than ~80 requests/minute, a named User-Agent and credit.
- **Rules and targets:** The official bracket system is still labelled "beta". Bracket rules last changed on October 21, 2025, when tutor restrictions were removed. The Game Changers list last changed on February 9, 2026, bringing it to 53 cards. Star City Games quoted Commander Format Panel member Gavin Verhey that day: "there won't be any changes to the core of the Brackets or Game Changers, however two cards have been added to the Game Changers list: Biorhythm... and Farewell." Use The Command Zone Ep. 658, "Commander Deckbuilding Template for the New Era" (published Feb 18, 2025), as the default targets. Its summary reads "RAMP: 10 CARD ADVANTAGE: 12 TARGETED DISRUPTION: 12 MASS DISRUPTION: 6 LANDS: 38 PLAN: 30", and the episode allows 10–12 ramp. For mana, use Karsten's land formula (31.42 + 3.13 × average MV − 0.28 × cheap ramp/draw) and his 2022 99-card colored-source table.
- **What rules can't do:** Role tagging should be a hybrid. Use Scryfall otags plus oracle-text rules first, and send only ambiguous cards to model judgment. Cut/add decisions, "off-plan" detection and combo robustness all need model judgment layered on deterministic scores. EDHREC synergy is useful as a candidate generator, but it is popularity-biased and should not decide cuts on its own.

---

## Key Findings

| Skill | Primary source | Access status (Oct 2026) | Main risk |
|---|---|---|---|
| 1. Intake | Pasted text in Arena/Moxfield/plain format; Commander Spellbook `card-list-from-url` / `card-list-from-text` | Text parsing is fully under your control. Moxfield and Archidekt JSON is unofficial | Moxfield is behind Cloudflare and has no official API |
| 2. Structure | Scryfall bulk data and oracle tags; Karsten formulas | Official, free, updated daily | Community tags change without notice |
| 3. Combos | Commander Spellbook API and bulk `variants.json.gz` | Official, documented, open source | Rate limits; the combo database grows continuously |
| 4. Cut/add | EDHREC (unofficial JSON), Scryfall search, Spellbook | EDHREC unofficial; Scryfall official | EDHREC terms not verified; popularity bias |
| 5. Orchestrator | All of the above, plus the official bracket rules from Wizards | n/a | The bracket system is still in beta |

---

## A. Decklist intake

### Export formats

**MTG Arena** (confirmed by a Wizards staff post in 2020, and the format still works today). Sections are labelled `Commander`, `Companion`, `Deck` and `Sideboard`, each separated by a blank line. In an unlabelled list, the first section is the main deck and the second is the sideboard. Lines can be `4 Basri Ket` or `4 Basri Ket (M21) 7`. The importer needs both the set code and the collector number to pin a printing, and it rejects leading zeros on collector numbers (Draftsim, "How to Import and Copy Decks into MTG Arena").
```
Commander
1 Alela, Artful Provocateur (ELD) 324

Companion
1 Lutri, the Spellchaser (IKO) 227

Deck
1 Temple of Silence (M20) 256
1 Watery Grave (GRN) 259
6 Plains (ELD) 251
```
Arena has no foil marker. Alchemy/rebalanced cards appear with an `A-` prefix (this is from general knowledge and was not re-verified for this report).

**Moxfield** text export ("Copy for Moxfield"). The format is `<qty> <name> (<SET>) <collector#> *F*`. `*F*` marks foil, `*A*` marks alter, and `#tag` / `#!globaltag` carry user tags. The Moxfield primer gist gives the grammar as `1 Cardname (SET) *F* *A* number #tag1 #!globaltag1`. The Forge bug report "Importing deck in Moxfield format skips foils" (issue #11005) confirms that `*F*` appears in real exports and breaks naive parsers.
```
Commander
1 Atraxa, Praetors' Voice (2X2) 190 *F*

Deck
1 Sol Ring (CMM) 400
1 Delighted Halfling (LTR) 158 *F* #Ramp
```
Moxfield's internal JSON has separate boards (`mainboard`, `sideboard`, `maybeboard`, `commanders`, `companions`, `attractions`, `stickers`, `signatureSpells`). Each card entry carries `quantity`, `finish`, `card.scryfall_id` and per-copy `printingData` (set, `cn`, finish). This field list comes from the mtgban Go package and the spoved/moxfield.cr models.

**Archidekt.** The deck JSON lists cards with quantity, card/oracle data, edition, `collectorNumber` and user categories. A card's categories include "Commander", "Maybeboard" and "Sideboard", plus custom roles such as "Ramp". Rows that were removed from a deck can still appear with `deletedAt` set, and you must skip them. This behaviour was documented in a GitHub PR from October 12, 2026 (wmhunter96/MTG #8). The text export follows the pattern `1x Card Name (set) 123 [Category]`. That pattern is from general knowledge and was not verified this cycle, so treat the category bracket syntax as something to test.

**MTGO.** This section is not re-verified in this research cycle and comes from general knowledge. The `.txt` export is `qty name` lines, with a blank line before the sideboard. The commander is usually placed in the sideboard section. The `.dek` export is XML with `<Cards CatID=… Quantity=… Sideboard="true|false" Name=…/>`. Neither format carries set codes in human-readable form or foil markers. Treat any 1-card sideboard in a 100-card MTGO list as the commander.

**Plain text.** The universal fallback is `quantity + name` per line with no headers (Culture of Gaming, "Fixing the 7 Most Common Import Mistakes"). Accept `1`, `1x` and `x1`, and accept common headers such as `Commander:`, `Commanders`, `EDH` (the decklist.gg import docs list these as accepted headers).

### Fetching decks by URL

| Site | Official API? | Endpoint that works (Oct 2026) | Notes |
|---|---|---|---|
| Moxfield | **No.** "Moxfield does not offer an official public API (see their FAQ)," per a September 2026 GitHub issue | `GET https://api2.moxfield.com/v3/decks/all/{publicId}`. Search: `/v2/decks/search?authorUserNames=…` | `v2/users/{user}/decks` was removed (404) by August 2026. Concurrent requests get rate-limited and return empty bodies, so throttle to ~1 request/second (architrice PR #11, Aug 29, 2026). Cloudflare/User-Agent checks apply. Login is gated by Turnstile and cannot be scripted (commander-lab PR #56, Oct 1, 2026) |
| Archidekt | Semi-official. Staff answer API questions on the forum, but no documentation or terms are published | `GET https://archidekt.com/api/decks/{id}/` (the `/small/` variant is deprecated). List: `/api/decks/v3/?ownerUsername=…` | The old `api/decks/cards/?owner=` endpoint now errors (Oct 2026). List queries cap at 1,000 results and do not return total counts (Archidekt forum) |
| Commander Spellbook | **Yes** | `GET /card-list-from-url?url=…` parses Moxfield, Archidekt, Deckstats and TappedOut URLs. `/card-list-from-text` parses pasted text | Best low-maintenance option: let Spellbook absorb the scraping risk |

**Terms of use:** I could not find published API terms or rate limits for Moxfield or Archidekt. Treat both as "personal, low-volume, cached, may break." Do not build bulk crawling on them.

### Name normalization rules
- **Resolve every line to a Scryfall `oracle_id`.** Spellbook also accepts oracle IDs anywhere it takes a decklist ("a card name, a number, or an oracle id," per the Spellbook backend docs).
- **Double-faced, modal DFC, split, adventure and flip cards.** Scryfall's canonical `name` is `Front // Back`. Accept a match on the front face alone, on either face for split cards, or on the full string, and look each one up against an index of `card_faces[].name`. Arena and some exports write only the front face.
- **Alchemy/digital cards.** `A-` prefixed names, and cards with `digital: true` and no paper printing, are not legal in paper Commander. Flag them rather than silently mapping them to the paper card.
- **Universes Beyond and alternate names.** A UB printing shares its `oracle_id` with any Universes Within version. Match the alternate name through Scryfall's `flavor_name` / `printed_name` fields, and always store the oracle name.
- **Normalization steps.** Apply Unicode NFKD, standardise apostrophes and quotes, collapse whitespace, and strip `*F*`, `*E*`, `#tags` and `[Category]` before lookup. Keep the set code, collector number and foil flag as printing metadata. They only matter for price.

**Implications for the skill:** Parse text first, because it is fully deterministic. For URLs, call Spellbook's `card-list-from-url` and fall back to direct Moxfield/Archidekt JSON with a 1 request/second throttle, a cache and a clear error message. Output a normalized list of `{oracle_id, name, qty, board, is_commander, is_companion, set, cn, finish}`. Fail loudly on unresolved names, show fuzzy suggestions using Scryfall `/cards/named?fuzzy=`, and stay under 2 requests/second.

**Open questions:** Moxfield's and Archidekt's terms of service for automated access were not found. The exact Archidekt and MTGO text-export syntax should be confirmed by exporting a test deck.

---

## B. Card data (Scryfall)

### Endpoints and limits
| Endpoint | Use | Hard limit |
|---|---|---|
| `GET /cards/named?exact=` / `?fuzzy=` | Single lookup and typo recovery | 2/s (500 ms) |
| `POST /cards/collection` | Batch lookup, up to 75 identifiers per call (apis.io profile) | 2/s |
| `GET /cards/search?q=` | Candidate generation (`otag:`, `id<=`, `legal:commander`) | 2/s |
| `GET /cards/random` | n/a | 2/s |
| `GET /cards/manifest` | Change tracking, 15,000 objects/page | 10/min |
| All other methods, including `/bulk-data` | n/a | 10/s (100 ms) |

These limits come from Scryfall's "API Rate Limits" page (scryfall.com/docs/api/rate-limits), which states: "/cards/search — 2/second (500ms)... /cards/collection — 2/second (500ms); /cards/manifest — 10/minute (6,000ms); All other methods — 10/second (100ms)... Recieving an HTTP 429 response will result in your access being limited for 30 seconds." Repeated abuse "may result in a temporary or permanent ban of your application." The file hosts on `*.scryfall.io` have no rate limits. Scryfall also asks for a descriptive `User-Agent` and an `Accept` header (apis.io Scryfall profile). Several GitHub projects fixed 429 errors in September–October 2026 after moving these four endpoints to 500 ms spacing (codwats/prism #279/#283; spellcontrol #2156; mtgban/sldownloader #27, Oct 1, 2026), which suggests the 2/s tier is a recent tightening.

Example request:
```
POST https://api.scryfall.com/cards/collection
Content-Type: application/json
User-Agent: edh-analyzer/0.1
{"identifiers":[{"name":"Sol Ring"},{"name":"Fable of the Mirror-Breaker"},{"set":"mh3","collector_number":"1"}]}
```
Abbreviated response:
```
{"object":"list","not_found":[],"data":[{"object":"card","oracle_id":"…","name":"Sol Ring",
 "mana_cost":"{1}","cmc":1.0,"type_line":"Artifact","oracle_text":"{T}: Add {C}{C}.",
 "color_identity":[],"produced_mana":["C"],"legalities":{"commander":"legal"},
 "game_changer":false,"edhrec_rank":1,"prices":{"usd":"1.50"}}, …]}
```

### Bulk data
- **Oracle Cards** has one object per `oracle_id` and is the right file for analysis. The size I could verify was 148 MB uncompressed, from a cached copy of Scryfall's bulk-data page marked "Last Updated 2025-01-15". It will be larger now.
- **Default Cards** has every English printing (462 MB in the same 2025-01-15 snapshot) and is only needed for printing-level prices.
- **All Cards** includes every language (2.15 GB in the same snapshot).
- **Rulings** (21.9 MB) is keyed on `oracle_id`.
- **Oracle Tags** was 5.76 MB, last updated 2026-10-21 21:00 UTC, according to the live bulk-data page snippet.
- **Update cadence:** Scryfall says bulk data is "collected once every 12 hours" and the page describes "daily exports." Prices "should be considered dangerously stale after 24 hours." For gameplay data, "downloading card data once per week or right after set releases would most likely be sufficient."

### Fields that matter
`oracle_id`, `name`, `layout`, `mana_cost`, `cmc`, `type_line`, `oracle_text`, `keywords`, `colors`, `color_identity`, `produced_mana`, `legalities.commander`, `game_changer`, `edhrec_rank`, `prices.{usd,usd_foil,eur,tix}`, `card_faces[]`, `reserved`, `digital`.

`game_changer` is a boolean that Scryfall added when the brackets launched ("Also available via the API: game_changer: true," Scryfall on X/Bluesky, Feb 2025). It lets you count Game Changers without keeping your own list.

**Multi-faced cards.** For layouts such as `transform`, `modal_dfc`, `split`, `adventure` and `flip`, the face-specific `mana_cost`, `oracle_text` and `type_line` live in `card_faces[]`. Top-level `cmc` and `color_identity` describe the whole card. Concatenate face texts for role tagging. For MDFC lands, treat the card as a spell for curve purposes and as a partial land for land count (see section D).

### Scryfall Tagger oracle tags (`otag:`)
- **What they are:** community-maintained "Oracle" tags that "describe the functional role of a card, such as removal, ramp, or draw." They are moderated, but "individual tags may be updated or reorganized at any time" (Scryfall "Tagger Tags" and "Tags" API docs).
- **How to query them:**
  - On the site and in the search API: `otag:` / `oracletag:` / `function:`.
  - As bulk data: the **Oracle Tags** file, which Scryfall now provides with a documented schema. Tag objects have a stable UUID `id`, `parent_ids` for the hierarchy, and taggings keyed by `oracle_id`. The bulk file contains direct taggings only, so you must walk `parent_ids` yourself.
  - There is no per-card tags endpoint (Scrython docs).
- **Outdated information:** a GitHub issue claimed "Oracle tags are not in Scryfall's bulk data" (cramt/progress-engine #15). That is now wrong.
- **Coverage evidence:** one project's importer attached tags to 36,041 of 38,705 cached cards (93%) out of 4,560 tags, with 0 unmatched oracle IDs (MangoPicante/mtg-recommender PR #4).
- **Aliases:** these live only in the bulk file. For example, `blink` is an alias of `flicker` (mattshoe/mtg-api PR #56).

**Implications for the skill:** Download Oracle Cards and Oracle Tags weekly, plus on set-release days. Build a local index keyed by `oracle_id` and keep API calls only for misses and fuzzy matches. Precompute each card's tag set with ancestors expanded. Get prices from the API, or from Default Cards no more than once a day, and label every price with its timestamp.

**Open question:** Scryfall's current terms for API use should be re-read before release. The secondary summary I found says data is free "for the primary purpose of creating additional Magic software, performing research, or creating community content." It prohibits implying Scryfall endorsement and putting Scryfall data behind paywalls or account walls, and it requires artist/copyright credit when showing art crops (libscry README quoting Scryfall's docs).

---

## C. Role taxonomy and structural targets

### Established templates
| Category | Command Zone original (Ep. 379) | Command Zone "New Era" (Ep. 658, 2025) | Common 2026 guides (Kraken the Meta, Spellweave) |
|---|---|---|---|
| Lands | 35–38 | **38** | 36–38 |
| Ramp | 10 | **10–12** (10 baseline) | 8–12 / 10–12 |
| Card draw/advantage | 10 | **12** | 8–12 |
| Targeted removal/disruption | 5 | **12** | 8–10 |
| Board wipes/mass disruption | 5 | **6** | 2–4 |
| Plan/strategy cards | 25 standalone + 10–12 enhancers + 7–8 enablers | **~30** (overlap allowed) | 25–30 |
| Protection / win cons | not separate | folded into Plan | win cons 2–4 (Spellweave) |

Sources: a Japanese summary of Command Zone Ep. 658 on note.com; OlliTapio/mtg-deck-optimizer `command_zone_template.md`; edh.fandom "Command Zone Template"; farseek.ai checklist; Kraken the Meta's 2026 guide; Spellweave 2026 guide.

**Conflicts to flag:**
1. The New Era totals add up to more than 100 because cards are meant to count in several categories. One GitHub transcription writes the plan as "~22" to force the total to 100. Your tool must allow double-counting.
2. An intermediate version on edh.fandom gives board wipes as 3–4 and removal as 10–12, while Ep. 658 says 6 mass disruption. That is a disagreement between versions, not an error.
3. Ep. 658 counts ramp as permanent acceleration only. Rituals such as Dark Ritual do not count.
4. The Command Zone discussed when to deviate from the template in Ep. 659, "The Problem with Deckbuilding Templates."

**EDHREC averages:** CoolStuffInc's "How many Lands do you need in a Commander deck? - Builders Series" (Apr 27, 2026) states: "Players are running somewhere between 33 (yeah, I know) and 38 Lands, averaging around 36 lands according to EDHREC." EDHREC's average-deck pages give per-commander type breakdowns through the JSON described in section G.

### Shifts by strategy and bracket
This section is my synthesis of common practice. No single primary source covers it, so treat the numbers as heuristics.

| Strategy | Adjustments |
|---|---|
| Voltron | Protection 6–10 (equipment and auras that grant hexproof/indestructible, counterspells). Fewer wipes (0–3). Cheap equipment counts as plan |
| Spellslinger | Lands 33–36 with many cantrips. Card-draw count goes up, and cheap interaction doubles as plan |
| Tokens / go-wide | Fewer symmetrical wipes (≤2). Add anthems/finishers as win conditions |
| Aristocrats | Sac outlets count as plan/engine. Recursion 3–6 |
| Landfall / lands | Lands 40–44+. "Ramp" overlaps with plan |
| Stax | Ramp is asymmetric, and the stax pieces count as mass disruption. Bracket 4+ only if they include mass land denial |
| Combo | Tutors 4–10, protection/counters up, 34–36 lands with fast mana |

On bracket effects: lower brackets favour more lands and slower interaction, while Bracket 4–5 decks run lower curves, fast mana and more tutors. The official game-length expectations (B1 at 9+ turns down to B4 at 4+) put numbers on that shift.

### Can roles be assigned automatically?
- **Rules on oracle text** work well for clear patterns: "Add {", "search your library for a … land", "draw (a|two|three) card", "destroy/exile target", "destroy all", "hexproof|indestructible" on others, "search your library for a card". They fail on conditional text, modal spells and engines.
- **Scryfall otags** are the best off-the-shelf labels (examples of real tags: `otag:ramp`, `otag:sacrifice-outlet`, `otag:tutor-any-card`). They are community-edited and very granular, so map the hierarchy down to your own small taxonomy.
- **Model judgment** is needed for whether a role is "on-plan" for this commander, for conditional ramp, and for engine-versus-one-shot distinctions where the tags are silent.
- **Prior art:** projects such as gab-25/mtg_deck_analyzer (Sept 2026) use functional tagging from card data. The jeisenback/infernal-machine engine reads bracket limits from single cards with rules and defers combos to Spellbook. The pattern that works is rules plus tags first, with an LLM pass for disagreements and low-confidence cards.

**Implications for the skill:** Tag every card with zero or more roles, each carrying a `confidence` and a `source` (otag, rule or model). Count a card toward every role it fills, and report weighted counts (see the taxonomy at the end). Read target ranges from a strategy profile that the orchestrator selects.

---

## D. Mana base analysis

### Karsten's colored-source table for 99-card decks
Source: Frank Karsten, "How Many Sources Do You Need to Consistently Cast Your Spells? A 2022 Update" (first published on ChannelFireball, now hosted on TCGplayer). It was published in 2022, but the exact date is unconfirmed: the Peasant Magic repost dates it "2/08/22", which could mean February 8 or August 2. The article defines "consistently" as "90 percent probability for one-drops, 91 percent probability on the play for two-drops and so on, assuming you drew enough lands."

| Cost | Sources (99-card) | Cost | Sources (99-card) |
|---|---|---|---|
| C (1-drop) | 19 | 5C | 14 |
| 1C | 19 | 4C | 15 |
| 2C | 18 | 3C | 16 |
| CC | 30 | 5CC | 20 |
| 1CC | 28 | 4CC | 22 |
| 2CC | 26 | 3CC | 23 |
| CCC | 36 | 4CCC | 26 |
| 1CCC | 33 | 3CCC | 28 |
| CCCC | 39 | 2CCC | 30 |
| 1CCCC | 36 | | |

**Method, so you can reproduce it:**
- **Target:** at least (89 + M)% probability of drawing N colored sources by turn M on the play, *conditional on having drawn at least M lands*. That works out to 90% for one-drops and 96% for seven-drops.
- **Deck assumption:** 41 lands in a 99-card deck.
- **Commander rules modelled:** the free mulligan and the Commander turn-one draw.
- **Mulligan policy (London rules):** mulligan the free 7 with 0, 1, 2, 6 or 7 lands. Mulligan later 7s with 0, 1, 6 or 7 lands, and 6-card hands with 0, 1, 5 or 6 lands. When bottoming, aim for about 3 lands and bottom off-color lands first.
- **How the numbers were produced:** Karsten used a Python Monte Carlo simulation. The pure hypergeometric core is P(X ≥ N) with X ~ Hypergeom(99, K sources, 7 + M − 1 cards seen on the play, +1 with the Commander draw). Reproduce the table by running a simulation that includes the mulligan policy and the land conditioning, and check it against the table above.
- **Secondary sites:** ScrollVault's figures (19 for C on turn 1, 30 for CC on turn 2, 18 for a turn-3 single pip) match Karsten. Its mana-rock weighting does not.

**Counting fractional sources (Karsten 2022):**
- Fetchlands count as a full source of every color they can fetch.
- Fabled Passage and Pathways count as a full source in two-color decks and about ⅔ in decks with three or more colors.
- Dual lands count as a full source for each color.
- Only untapped lands count for turn-1 requirements.
- Mana rocks (Signets, Arcane Signet) count as ¾ of a source for each color, and only for spells with MV 3 or more.
- Mana dorks count as ½ of a source, and only for MV 2 or more.
- Two-mana land ramp (Farseek, Rampant Growth) counts as ¾, and only for MV 3 or more.
- Cultivate counts only for MV 4 or more, and is worth about ½ for MV 5 or more.
- Each Treasure counts as ¼.
- Exotic Orchard counts as ¾ of any color, or a full source when the opponents' colors are known. Fellwar Stone counts as ½ (¾ when opponents' colors are known).
- Non-mythic MDFC lands count as 0.8 of a source, mythic ones as a full source.
- Gold cards: add 1 to each requirement and also check the combined count of sources that make either color.

### Land count
Karsten ("How Many Lands Do You Need in Your Deck? An Updated Analysis," TCGplayer) gives this formula for 99-card decks: **lands = 31.42 + 3.13 × average MV of spells − 0.28 × number of cheap card-draw or mana-ramp spells**. MDFCs count partially, and the average MV is computed with land/spell MDFCs counted as their front face. The formula is derived as 99/60 × (19.59 + 1.90 × avgMV + 0.27) − 1.35. Karsten calls the 1.35 adjustment for the free mulligan and draw a back-of-the-envelope estimate (ScrollVault summary).

Worked examples:

| Avg MV | Cheap ramp/draw | Recommended lands |
|---|---|---|
| 2.5 | 15 | 35.0 |
| 3.0 | 12 | 37.4 |
| 3.5 | 10 | 39.6 |
| 4.0 | 8 | 41.7 |

A simulation by FreeMully, using a Trostani deck with avgMV 3.51 and 13 cheap pieces, landed at 38.8, "right where our simulation stopped improving." FreeMully counts "cheap" as MV 3 or less. The older community rule "40 lands less 1 for every 2 mana rocks" (The Mana Base) is roughly consistent with this.

**Conflict to flag:** Karsten's formula usually gives 37–40 lands, while EDHREC's real-world average is about 36. Your report should show both and explain the gap: most players under-build lands.

### Land quality and pips
- **Pip counting:** count colored pips per color across spells, weighted toward early-MV cards. Use the most demanding card per color (for example, a CC two-drop) to set the requirement from the table. Hybrid and Phyrexian pips count for each color they can pay (gab-25 design).
- **Quality scoring** (my proposed heuristic):
  - Untapped dual or fetch = 1.0.
  - Conditional untapped (check, fast, slow lands) = 0.8.
  - Tapped dual or tri = 0.6, rising to 0.75 with an upside such as cycling or scry.
  - Utility colorless land = 0.5 for colored count but positive for plan.
  - Basic = 1.0 for its color.
- **Warnings to generate:** more than 6 tapped lands in Bracket 3 or above; any color below its table requirement; colorless-only land count above 10% in decks with three or more colors.
- **Cycling lands and MDFCs:** count MDFC lands as 0.8 (non-mythic) or 1.0 (mythic) lands. Count cycling lands as full lands.
- **Cheap rocks** count toward the formula's ramp term, not as lands.

**Implications for the skill:** Implement both Karsten formulas exactly as given and expose their assumptions. Compute fractional sources per color, a tapped-land count and a per-color deficit. Phrase the output as a recommendation, for example: "add 2 lands" or "swap 3 basics for dual lands."

---

## E. Combo detection (Commander Spellbook)

### API
- **Base URL:** `https://backend.commanderspellbook.com/`. The root lists `variants`, `features`, `cards`, `templates`, `find-my-combos`, `estimate-bracket`, `explain-query`, `card-list-from-url` and `card-list-from-text`.
- **Schema:** the OpenAPI document is at `/schema/`, with Swagger at `/schema/swagger/`. Responses use camelCase.
- **Clients:** generated Python (`spellbook_client`) and TypeScript (`@space-cow-media/spellbook-client`) clients are available.
- **Bulk data:** `https://json.commanderspellbook.com/variants.json.gz` contains all variants and aliases. The docs say: "Do not use the HTTP API to export the whole dataset."
- **Guidelines** (from the Spellbook backend developer docs, page updated October 19, 2026):
  - Name your service in the User-Agent.
  - "80 requests per minute should be a safe rate."
  - "Always handle 429."
  - "Please credit us and link back to commanderspellbook.com."
- **Bracket estimation:** the Spellbook backend developer announced `estimate-bracket` on Moxfield's feedback board. It returns "bracket-relevant information, mainly two card combos classified based on their requirements." Moxfield has since merged a Spellbook-backed bracket integration.

Example request (verified by a third-party project on 2026-10-21):
```
POST https://backend.commanderspellbook.com/find-my-combos/
Content-Type: application/json
User-Agent: edh-analyzer/0.1
{"commanders":[{"card":"Kinnan, Bonder Prodigy","quantity":1}],
 "main":[{"card":"Basalt Monolith","quantity":1},{"card":"Sol Ring","quantity":1}, …]}
```
Abbreviated response:
```
{"results":{
  "identity":"GU",
  "included":[{"id":"…","uses":[{"card":{"name":"Kinnan, Bonder Prodigy"}},{"card":{"name":"Basalt Monolith"}}],
     "produces":[{"feature":{"name":"Infinite colorless mana"}}],
     "bracketTag":"…","manaNeeded":"{3}","identity":"GU","legalities":{"commander":true},
     "popularity":12345,"easyPrerequisites":"…","notablePrerequisites":"…","description":"1. … 2. …"}],
  "almostIncluded":[ … combos missing exactly one card … ],
  "includedByChangingCommanders":[…], "almostIncludedByAddingColors":[…], …}}
```
The `included`, `almostIncluded`, `uses`, `produces`, `bracketTag`, `manaNeeded`, `identity`, `legalities` and `popularity` keys were verified (jeisenback/infernal-machine #487). The other buckets and the prerequisite/steps field names are from my knowledge of the schema, so confirm them against `/schema/`.

### Complete versus near-complete combos
- `included` lists every piece present in the deck plus the commanders.
- `almostIncluded` is **one card away**. Combos two or more cards away are not returned, so a "2 missing" search needs the bulk file and local set matching.
- Each variant includes prerequisites, a step description, results (features such as "Infinite colorless mana" or "Win the game"), `manaNeeded`, color identity, legality, popularity (deck count) and a bracket tag. Variants now also carry a community `salt` score (0–4, shown once there are at least 5 votes in the past year).

### Robustness scoring (proposed)
Score each combo from 0 to 100 using these factors:

| Factor | Weight | How to compute |
|---|---|---|
| Pieces | 25 | 2 = 25, 3 = 15, 4+ = 5. A commander piece adds +5 because the commander is always available |
| Mana to assemble and execute | 15 | Sum of piece MV plus `manaNeeded`. 6 or less = full score |
| Tutor access | 20 | Count deck tutors that can find each piece (otags `tutor`, `tutor-creature`, etc.) |
| Redundancy | 10 | Other included combos sharing the same outcome or pieces |
| Fragility | 15 | Graveyard-dependent pieces lose points against graveyard hate. Creature pieces are exposed to wipes. Artifact/enchantment pieces are exposed to Disenchant effects |
| Outcome | 15 | A "Win the game" result scores full. Infinite mana, tokens or damage need an outlet: check whether one is in the deck |

**Implications for the skill:** Make one `find-my-combos` call per analysis and cache it keyed by the sorted card list. Use the bulk file for two-missing combos and for offline runs. Always print the Spellbook credit and link. Use `bracketTag` together with each piece's MV to flag early two-card combos for Bracket ≤3 (see section F).

---

## F. Brackets and power level

**Status:** the system is still "beta." Wizards' February 9, 2026 update promised no bracket-level changes until the Commander Format Panel had seen at least one 2026 MagicCon. It said that "you will likely see us drop the beta tag later this year." Third-party trackers report no Commander changes in the 2026 banned-and-restricted announcements. ScrollVault (Oct 2, 2026) covers the March 23, May 18, June 29 and August 10 announcements. Kraken the Meta puts the list at "53, as of 8 August 2026" and says "Neither the 18 May nor the 29 June 2026 Banned and Restricted announcements touched the brackets or the Game Changers list."

**Check before shipping:** a banned-and-restricted announcement was expected around October 12, 2026 (TabletopMeta). I found no evidence that it changed Commander, but verify against Wizards before shipping.

| Bracket | Game Changers | Mass land denial | Extra turns | Two-card combos | Expected game length |
|---|---|---|---|---|---|
| 1 Exhibition | 0 (thematic exceptions allowed after a pregame talk) | No | No chaining | No | 9+ turns |
| 2 Core | 0 | No | No chaining | No intentional ones | 8+ |
| 3 Upgraded | Up to 3 | No | No chaining | None before turn 6 | 6+ |
| 4 Optimized | Any | Allowed | Allowed | Allowed | 4+ |
| 5 cEDH | Any | Allowed | Allowed | Allowed | Any |

**Tutors:** since the October 21, 2025 update, there is no tutor restriction in any bracket. Wizards wrote that it would "remove the tutor restrictions from Commander Brackets entirely and rely on Game Changers to catch the most efficient tutors." The same update separated Bracket 2 from precons and added turn expectations to each bracket.

**Game Changers (53, current as of the February 9, 2026 update).** The list below was compiled from secondary sources. Pull the authoritative version from Scryfall `is:gamechanger` or the `game_changer` field.
- White: Drannith Magistrate, Enlightened Tutor, Farewell, Humility, Serra's Sanctum, Smothering Tithe, Teferi's Protection.
- Blue: Consecrated Sphinx, Cyclonic Rift, Fierce Guardianship, Force of Will, Gifts Ungiven, Intuition, Mystical Tutor, Narset, Parter of Veils, Rhystic Study, Thassa's Oracle.
- Black: Ad Nauseam, Bolas's Citadel, Braids, Cabal Minion, Demonic Tutor, Imperial Seal, Necropotence, Opposition Agent, Orcish Bowmasters, Tergrid, God of Fright, Vampiric Tutor.
- Red: Gamble, Jeska's Will, Underworld Breach.
- Green: Biorhythm, Crop Rotation, Gaea's Cradle, Natural Order, Seedborn Muse, Survival of the Fittest, Worldly Tutor.
- Multicolor: Aura Shards, Coalition Victory, Grand Arbiter Augustin IV, Notion Thief.
- Colorless: Ancient Tomb, Chrome Mox, Field of the Dead, Glacial Chasm, Grim Monolith, Lion's Eye Diamond, Mana Vault, Mishra's Workshop, Mox Diamond, Panoptic Mirror, The One Ring, The Tabernacle at Pendrell Vale.

The blue list is my reconstruction to reach 53 and should be checked against Scryfall. The ten cards removed in October 2025 were Expropriate, Jin-Gitaxias, Core Augur, Sway of the Stars, Vorinclex, Voice of Hunger, Kinnan, Urza, Winota, Yuriko, Deflecting Swat and Food Chain.

**Programmatic estimation:** Spellbook's `estimate-bracket` takes a decklist and returns bracket-relevant combo classifications. Moxfield has integrated it. Scryfall's `game_changer` handles the Game Changer count. Mass land denial and extra turns need oracle-text rules: "destroy all lands", "lands don't untap", "take an extra turn". Several third-party calculators exist (ScrollVault, commanderbrackets.com), but none publishes an API I could verify.

**Implications for the skill:** Compute a bracket floor from hard rules: Game Changer count, mass land denial, chained extra turns, and two-card combos with assembly MV low enough to finish before turn 6. Report it as "minimum bracket by rules." Present any speed or intent judgment as a separate, explicitly model-based estimate, because Wizards stresses that intent matters most.

---

## G. Cut/add candidates and card evaluation

### EDHREC data
- **Access:** EDHREC has no official API. The pyedhrec README says "EDHREC does not provide an API." The site's own front end reads public JSON, for example `https://json.edhrec.com/pages/commanders/{slug}.json`, which several Apify scrapers use without a key.
- **What the per-commander JSON contains:** `num_decks`, rank, top cards, high-synergy cards, new cards, card lists by type (creatures, instants, mana artifacts, utility lands and so on), each card's `synergy`, inclusion count and potential decks (inclusion rate = decks ÷ potential decks), themes with deck counts, similar commanders, bracket and budget breakdowns, average deck and salt score (Apify actor field lists, October 2026).
- **Refresh rate:** EDHREC updates daily, according to the scrapers.
- **Terms of use:** I could not verify EDHREC's terms for automated access. Treat it as low-volume and cached, attribute it, and do not redistribute its data.

### What synergy means and where it fails
EDHREC's definition: synergy = (the card's inclusion rate in this commander's decks) − (its inclusion rate in all eligible decks of overlapping color identity). The EDHREC Wiki example: Eldrazi Displacer is in 86% of Rasputin decks and 11% of other U/W decks, giving +75%.

Weaknesses:
- **Popularity feedback.** EDHREC's own article says synergy "doesn't determine… how powerful or useful a card is." Generic staples score near zero or negative (Path to Exile at −1% for The Ur-Dragon). Because the inclusion-sorted average deck pulls power upward, the aggregate list "can creep up in power" (Mulligo).
- **New cards** have little data and very noisy synergy.
- **Small-sample commanders** produce extreme values.
- **Bracket-blind.** Data is not split by bracket unless you use EDHREC's bracket filters.

### Heuristics for choosing cuts
Written sources for these are thin, so the list below is a synthesis. The template and its deviations are from the Command Zone, Eps. 658 and 659.
1. **Role surplus:** cut from roles above their target range first.
2. **Mana efficiency:** within a role, cut the highest-MV card with the same effect (for example, a 4-MV rock when a 2-MV rock fills the slot).
3. **Off-plan:** a card that matches no commander theme or tag cluster and has low synergy.
4. **High cost, low impact:** MV 6 or more without a game-winning or game-swinging effect.
5. **Win-more:** effects that only matter when you are already ahead, such as anthems in decks without a go-wide base.
6. **Conditional cards** whose condition the deck rarely meets.
7. **Bracket violations:** Game Changers beyond the bracket cap, or mass land denial in Bracket ≤3.

### Filtering candidates
- **Color identity and legality:** Scryfall `id<=` the commander's identity, `legal:commander`, and `game_changer` / bracket caps.
- **Budget:** use Scryfall `prices.usd`. Scryfall's prices come from TCGplayer (USD), Cardmarket (EUR) and Cardhoarder (TIX) and are refreshed once a day, so show them as estimates with a date. EDHREC also shows Card Kingdom and TCGplayer prices.

### Pairing a cut with an add
Score each swap as Δ(role-gap closure) + Δ(card quality: synergy, efficiency, `edhrec_rank`) − Δ(price over budget) − bracket penalty. Pair greedily: the most over-target role gives a cut, and the most under-target role receives an add of similar or lower MV. Keep the land count and curve neutral unless the mana analysis says otherwise.

**Implications for the skill:** Generate candidates from EDHREC (if reachable), Scryfall otag searches filtered by identity, and Spellbook `almostIncluded` combos. Rank them deterministically. Then use the model to write the reason for each swap and veto swaps that break the deck's theme.

---

## H. Prior art

Licenses were not verified unless stated. Check each repository before reusing code.

| Project | What it does | Language | Reusable parts | Lesson |
|---|---|---|---|---|
| SpaceCowMedia/commander-spellbook-backend | Combo database, variant generation, bracket estimation, decklist parsing | Python/Django | Generated SDKs, bulk JSON, query language | Use its API rather than re-implementing combo search |
| jeisenback/infernal-machine | Deck tuner with `brackets.py` (Game Changers, mass land denial, extra turns, tutors) and a cached Spellbook client | Python | Bracket-rule logic; caching pattern keyed by sorted card names | Rules on single cards plus Spellbook for combos |
| gab-25/mtg_deck_analyzer | Curve, color sources against Karsten, functional tagging, hypergeometric opening-hand odds | Python | Statistics design (#32, Sept 2026) | Present Karsten verdicts in plain language |
| MangoPicante/mtg-recommender | Imports oracle tags and attaches them to cards | Python | Oracle-tag importer (joins on `oracle_id`) | 93% tag coverage; walk the tag hierarchy |
| OlliTapio/mtg-deck-optimizer | Optimizer built on the Command Zone template | n/a | Template definition file | Encode overlapping categories |
| Combinator (jamese.dev) | Finds combos in Moxfield, Archidekt and MTGGoldfish decks | Python/FastAPI | Spellbook call pattern | Spellbook stopped shipping its full database to the client in early 2024; use the API or bulk file |
| Melrakkiie/Tamiyo | Deck statistics with a Spellbook combos tile | n/a | API contract and credit-line UX | Gzip, User-Agent and credit link |
| pyedhrec | EDHREC wrapper (top cards, average deck, synergy lists) | Python | Endpoint coverage | Uses in-memory caching to avoid hammering EDHREC |
| Scrython 2.x | Scryfall wrapper with per-endpoint rate limits, bulk data and tags | Python | Drop-in client | Enforces 2/s and 10/s automatically |

---

## Recommended role taxonomy

| Role | Definition | Primary signal | Edge cases and resolution |
|---|---|---|---|
| `land` | Land cards | type_line | MDFC land = 0.8 land plus its spell role |
| `ramp` | Permanent mana acceleration: rocks, dorks, land search, cost reducers | otag ramp/mana-rock/mana-dork; "Add {" on non-lands; "search … land … battlefield" | Rituals = `ritual`, not ramp. Conditional ramp (e.g., tribal) = 0.5 |
| `card_advantage` | Net card gain. Subtypes: `draw_engine` (repeatable) and `draw_burst` (one-shot) | otag draw/card-advantage; "draw" | Cantrips = 0.25. Impulse draw counts. Looting is selection, not advantage |
| `targeted_interaction` | Removes or neutralises one threat: removal, counterspells, bounce | otag removal/counterspell | Graveyard hate counts as 0.5 unless it hits a whole graveyard |
| `mass_interaction` | Wipes and one-sided wipes | otag board-wipe/sweeper; "destroy all", "each creature" | Mass bounce counts. Symmetrical wipes in tokens decks get flagged |
| `protection` | Protects your board or commander: hexproof, indestructible, phasing, counter-protection | otag protection/gives-hexproof | Counterspells count for both interaction and protection |
| `tutor` | Searches for a non-land card | otag tutor-* | Land tutors = ramp |
| `recursion` | Returns cards from the graveyard | otag recursion/reanimation | n/a |
| `wincon` | Ends the game or presents lethal | Combo outcome "win"; otag win-condition; model judgment | Often needs model judgment |
| `engine`/`synergy` | Plan cards that match the commander's theme | Model judgment plus EDHREC synergy | n/a |
| `stax` / `mld` / `extra_turn` | Bracket-relevant flags | Rules on oracle text | Feed into the bracket check |

Ambiguity rule: a card may hold up to 3 roles at weights of 1.0, 0.5 or 0.25. Agreement between rules and otags gives high confidence. Disagreement or a missing signal sends the card to the model, which must cite the oracle text behind its choice.

## Recommended default role-count targets (Bracket 2–3, midrange)

| Role | Target | Acceptable range | Source basis |
|---|---|---|---|
| Lands | Karsten formula (usually 37–38) | 35–40 | Karsten 2022; Command Zone Ep. 658 |
| Ramp | 10 | 8–12 | Command Zone Ep. 658 |
| Card advantage | 12 | 9–14 | Command Zone Ep. 658 |
| Targeted interaction | 10 | 8–12 | Between Ep. 658 (12) and 2026 guides (8–10) |
| Mass interaction | 4 | 2–6 | Range spans the guides (2–4) and Ep. 658 (6) |
| Protection | 4 | 2–8 (voltron 6–10) | Synthesis |
| Tutors | 2 | 0–4 (combo 4–10) | Synthesis; no bracket cap since Oct 2025 |
| Win conditions | 4 | 2–6 | Spellweave 2026 (2–4), widened |
| Recursion | 3 | 0–6 | Synthesis |

The orchestrator should apply the strategy offsets from section C, and the report should say which profile was used.

## Risks

**Data access**
- Moxfield has no official API. It uses Cloudflare and Turnstile, and endpoints have changed recently (Aug 2026).
- Archidekt and EDHREC are undocumented, with unknown terms. Moxfield's, Archidekt's and EDHREC's terms of service were not found and must be checked before any public release.
- Scryfall bans clients that keep drawing 429 responses.
- Spellbook asks for ≤80 requests/minute.

**Staleness**
- The Game Changers list and bracket rules are still in beta and could change at any announcement. Version and date your rule table.
- Scryfall prices go stale after 24 hours.
- Oracle tags change daily.
- EDHREC synergy lags for new sets.
- Spellbook adds combos continuously, so record the bulk-file timestamp.

**Licensing**
- Card text and images are owned by Wizards under its Fan Content Policy.
- Scryfall data must not be paywalled or presented as endorsed by Scryfall.
- Spellbook requests credit and a link.
- Open-source code licenses were not verified.

**Needs model judgment rather than rules**
- On-plan versus off-plan, win-more, conditional ramp, and engine versus burst draw where tags are silent.
- Combo outlet availability, and whether a combo is "early" for Bracket 3.
- Intent-based bracket placement.
- Final cut/add rationale.

**Unverified in this report**
- MTGO and Archidekt text-export syntax.
- Spellbook response fields beyond those listed as verified.
- The blue Game Changers entries.
- Current Oracle Cards bulk-file size.
- Whether the October 12, 2026 banned-and-restricted announcement changed anything for Commander.