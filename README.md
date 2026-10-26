# EDH deck skills

Five Claude [Agent Skills](https://code.claude.com/docs/en/skills) that review a Magic: The Gathering Commander (EDH) deck. They report its structure and mana base, the combos it contains or nearly contains, where it sits in the official Commander Brackets, and a prioritized list of cards to cut and add, with a reason for each swap.

The scripts do the counting and the math. Claude makes the judgment calls the rules can't: which cards are engine pieces or off-plan for this commander, whether a combo has a real outlet, the bracket estimate, and the final wording of every swap.

| Skill | What it does |
|---|---|
| `edh-deck-intake` | Parses a decklist (Arena, Moxfield, Archidekt, MTGO, TappedOut, plain text, or a deck URL) and resolves every card against Scryfall into `deck.json` |
| `edh-deck-structure` | Tags card roles (ramp, draw, interaction, protection, tutors, recursion, win conditions, engine, tokens), compares them with strategy-specific targets, and checks the mana base with Frank Karsten's land formula and colored-source table |
| `edh-combo-finder` | Finds complete and near-complete combos with Commander Spellbook and scores how robust each one is |
| `edh-cut-add` | Scores cuts and adds and pairs them into swaps; optionally favours or restricts adds to cards in your collection |
| `edh-deck-review` | The orchestrator: runs the other four and writes one consistent report |

## Install

**claude.ai / Claude desktop app:** build the `.skill` files and upload each one in your Skills settings:

```
python tools/package_skills.py      # writes dist/*.skill
```

**Claude Code:** copy or symlink the skill folders into your personal skills folder, keeping all five side by side:

```
mkdir -p ~/.claude/skills
ln -s "$PWD"/skills/edh-* ~/.claude/skills/
```

If you sign in to Claude Code with your claude.ai account, skills saved to that account also sync into `~/.claude/skills/synced/`.

The scripts use only the Python standard library (Python 3.9+).

## Use

Ask Claude for a deck review and share a decklist or a Moxfield/Archidekt link. The orchestrator skill does the rest. To run the pipeline by hand from the repo root:

```
python skills/edh-deck-review/scripts/pipeline.py phase1 --work work/ --deck deck.txt
# review work/roles.json["needs_review"] and write work/overrides.json
python skills/edh-deck-review/scripts/pipeline.py phase2 --work work/ --strategy midrange --bracket 3 \
    [--budget 10] [--collection my_collection.csv --collection-mode prefer|only]
```

`python skills/edh-deck-review/scripts/pipeline.py --help` lists every option.

### Network access

The scripts call Scryfall, Commander Spellbook, EDHREC and Moxfield/Archidekt directly. On your own machine that normally just works. Sandboxed environments often block these hosts:

- **Claude Code's optional Bash sandbox:** allow the domains below in its network settings.
- **Claude Code cloud sessions:** set the environment's network access to **Custom** and add the domains.
- **claude.ai's sandbox:** use the browser fallback. JavaScript snippets in each skill's `scripts/browser/` fetch the data from a browser tab, in exactly the format the scripts accept. See `skills/edh-deck-intake/references/browser_fetch.md`.

Domains: `api.scryfall.com`, `data.scryfall.io`, `backend.commanderspellbook.com`, `json.commanderspellbook.com`, `json.edhrec.com`, `api2.moxfield.com`, `archidekt.com`.

## Repository layout

```
skills/            the five skills (SKILL.md, scripts/, references/, evals/)
dev/               synthetic test fixtures and the script that builds them
docs/research/     the research brief and report the skills were designed from, and the later improvement brief
docs/examples/     an example report
tools/             packaging, shared-file sync, and an offline smoke test
```

Some files are deliberately duplicated so each skill works on its own:
- `edh_common.py`
- `tag_roles.py` and `scryfall_data.py` (copies in cut-add)
- `browser_fetch.md`

Edit the canonical copy (see `tools/sync_shared.py`), then run `python tools/sync_shared.py`.

## Testing

```
python tools/smoke_test.py          # offline end-to-end run on dev/fixtures (no network)
python tools/sync_shared.py --check
```

Each skill's `evals/` folder holds test cases in the format `claude plugin eval` reads (a prompt, input files, and graders describing a good result).

The fixtures in `dev/fixtures/` are synthetic: a 100-card Meren deck with oracle text written for testing, a small oracle-tags file, and a canned Commander Spellbook response. Rebuild them with `python dev/build_fixture.py dev/fixtures`.

## Data sources and credits

- **[Scryfall](https://scryfall.com)**: card data, oracle tags, prices. Respect the rate limits (2 requests/second on search and lookup endpoints). Don't paywall the data or imply endorsement.
- **[Commander Spellbook](https://commanderspellbook.com)**: combos and bracket tags. Credit it and link back wherever combo results are shown; keep to about 80 requests per minute.
- **[EDHREC](https://edhrec.com)**: synergy and inclusion data, from an unofficial endpoint with no published terms. Keep usage low, cache it, and attribute it.
- **Moxfield / Archidekt**: deck import, from unofficial endpoints that may break.
- **Mana math**: Frank Karsten's colored-source and land-count research. **Role targets**: The Command Zone's deckbuilding template (Ep. 658).
- **Brackets**: the official Commander Brackets (beta). The rules and Game Changers list are dated in `skills/edh-deck-review/scripts/bracket_rules.json`; re-check them after each Wizards announcement.

Magic: The Gathering card names and text are property of Wizards of the Coast. This project is unofficial Fan Content permitted under the Wizards of the Coast Fan Content Policy. It is not approved or endorsed by Wizards.
