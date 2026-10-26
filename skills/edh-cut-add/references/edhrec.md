# EDHREC data (unofficial)

- No official API ("EDHREC does not provide an API", pyedhrec README). The site's front end reads public JSON, e.g. `https://json.edhrec.com/pages/commanders/{slug}.json`; several scrapers use it without a key.
- Slug: lowercase, punctuation removed, spaces → hyphens; partner pairs are both slugs joined alphabetically (`candidates.edhrec_slug`). If a page 404s, the slug rule may be off for that card. Try the user's link or search the site.
- Contents (per scraper field lists, Oct 2026): `num_decks`, rank, top cards, high-synergy cards, new cards, lists by card type, per-card `synergy`, inclusion count and potential decks (inclusion rate = decks ÷ potential decks), themes, similar commanders, bracket and budget breakdowns, average deck, salt.
- The JSON layout is undocumented; `candidates.py` walks it looking for objects with `name` plus `synergy`/`num_decks`/`inclusion`, so it survives moderate reshuffles.
- Refresh: daily.
- Terms for automated access: not found. Low volume, cache for a day, attribute EDHREC, don't redistribute its data.

## Synergy
synergy = (inclusion rate in this commander's decks) − (inclusion rate in all decks that could play the card). EDHREC Wiki example: Eldrazi Displacer in 86% of Rasputin decks vs 11% of other W/U decks → +75%.

Weaknesses:
- Says nothing about power ("doesn't determine… how powerful or useful a card is", EDHREC). Staples score ~0 or negative (Path to Exile −1% for The Ur-Dragon).
- Popularity feedback: the inclusion-sorted average deck creeps up in power (Mulligo).
- New cards have little data; small-sample commanders give extreme values.
- Bracket-blind unless you use EDHREC's bracket filters.
