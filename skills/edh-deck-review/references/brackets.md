# Commander Brackets (beta) — as of October 2026

Status: still labelled beta. Rules last changed **2025-10-21** (tutor restrictions removed; Bracket 2 separated from precons; turn expectations added). Game Changers last changed **2026-02-09** (Biorhythm and Farewell added → 53 cards). Wizards said then that core changes would wait until the Commander Format Panel had seen at least one 2026 MagicCon and that the beta tag would likely drop "later this year". Trackers (ScrollVault Oct 2 2026; Kraken the Meta, "53, as of 8 August 2026") report no Commander changes in the Mar 23, May 18, Jun 29, Aug 10 2026 announcements. An announcement around Oct 12 2026 was not verified, so check Wizards before relying on this.

| Bracket | Game Changers | Mass land denial | Extra turns | Two-card combos | Expected game length |
|---|---|---|---|---|---|
| 1 Exhibition | 0 (thematic exceptions after a pregame talk) | No | No chaining | No | 9+ turns |
| 2 Core | 0 | No | No chaining | No intentional ones | 8+ |
| 3 Upgraded | Up to 3 | No | No chaining | None before turn 6 | 6+ |
| 4 Optimized | Any | Allowed | Allowed | Allowed | 4+ |
| 5 cEDH | Any | Allowed | Allowed | Allowed | Any |

**Tutors:** no restriction in any bracket since 2025-10-21; Wizards relies on the Game Changers list to catch the most efficient tutors.

**Game Changers:** use Scryfall's `game_changer` field or `is:gamechanger`; the bundled list in `scripts/bracket_rules.json` is a fallback compiled from secondary sources (blue entries reconstructed). Removed on 2025-10-21: Expropriate, Jin-Gitaxias Core Augur, Sway of the Stars, Vorinclex Voice of Hunger, Kinnan, Urza, Winota, Yuriko, Deflecting Swat, Food Chain.

**Programmatic estimation:** Spellbook `estimate-bracket` (combo classifications; Moxfield integrates it); Scryfall `game_changer` for counts; oracle-text rules for MLD ("destroy all lands", "lands don't untap") and extra turns ("take an extra turn"). No third-party calculator (ScrollVault, commanderbrackets.com) publishes a verified API.

**How to report:** a "minimum bracket by rules" floor from the hard rules, and a separately labelled model estimate based on speed and intent. Wizards stresses that intent and the pregame conversation matter most.
