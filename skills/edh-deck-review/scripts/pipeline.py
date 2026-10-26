#!/usr/bin/env python3
"""Run the EDH deck-analysis skills in order. Two phases, because role tagging needs a
model review step in the middle.

  phase1  intake -> role tags -> combos          (writes deck.json, roles.json, combos.json)
          then the model reviews roles.json["needs_review"] and writes overrides.json
  phase2  mana -> structure -> bracket floor -> candidates -> swaps
          (writes mana.json, structure.json/.md, bracket.json, candidates.json, swaps.json/.md)

The sibling skills are found next to this skill's folder (edh-deck-intake, edh-deck-structure,
edh-combo-finder, edh-cut-add), or pass --skills-dir. Each step is an ordinary script call, so
if one fails you can rerun that step by hand with the command printed in the log.

Blocked network (sandbox proxy refuses Scryfall/Spellbook/EDHREC/Moxfield)? Fetch the data with the browser
snippets in edh-deck-intake/references/browser_fetch.md and pass the saved files:
  phase1: --parsed-json (deck), --cards-json (cards), --spellbook-response (combos)
  phase2: --edhrec-json, --candidates-json, --offline (skip live EDHREC/Scryfall attempts)

Usage:
  python pipeline.py phase1 --work DIR (--deck deck.txt|URL | --parsed-json parsed.json) [--commander NAME]
                            [--cards-json cards.json | --cards-file oracle-cards.jsonl.gz --tags-file oracle-tags.jsonl.gz]
                            [--spellbook-response spellbook.json]
  python pipeline.py phase2 --work DIR [--strategy polymorph] [--bracket 3] [--budget 10] [--protect NAME ...]
                            [--edhrec-json edhrec.json] [--candidates-json supplied.json] [--offline] [--max-swaps 10]
                            [--collection my_collection.csv [--collection-mode prefer|only] [--collection-cards owned.json]]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ["edh-deck-intake", "edh-deck-structure", "edh-combo-finder", "edh-cut-add"]


def find_skills(skills_dir: str | None) -> dict[str, Path]:
    roots = [Path(skills_dir)] if skills_dir else []
    roots += [HERE.parent.parent, HERE.parent.parent.parent, Path.home() / ".claude" / "skills",
              Path("/mnt/skills/user"), Path("/mnt/skills/private"), Path("/mnt/skills/plugins")]
    found = {}
    for n in NAMES:
        for r in roots:
            hits = [r / n] + (list(r.glob(f"*/{n}")) if r.exists() else [])
            for h in hits:
                if (h / "scripts").is_dir():
                    found[n] = h / "scripts"
                    break
            if n in found:
                break
        if n not in found:
            sys.exit(f"Cannot find the {n} skill. Pass --skills-dir (the folder that contains the skill folders).")
    return found


def run(cmd: list, allow_fail: bool = False) -> int:
    print("$ " + " ".join(str(c) for c in cmd), file=sys.stderr, flush=True)
    rc = subprocess.call([str(c) for c in cmd])
    if rc and not allow_fail:
        sys.exit(f"step failed (exit {rc}); fix the problem and rerun the command above")
    return rc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["phase1", "phase2"])
    ap.add_argument("--work", required=True)
    ap.add_argument("--skills-dir")
    ap.add_argument("--deck"); ap.add_argument("--commander", action="append")
    ap.add_argument("--cards-file"); ap.add_argument("--tags-file")
    ap.add_argument("--parsed-json", help="already-parsed deck (browser snippet moxfield_deck.js); skips fetching/parsing")
    ap.add_argument("--cards-json", help="card data from outside (browser snippet cards_scryfall.js, or slim cards)")
    ap.add_argument("--spellbook-response", help="offline: saved find-my-combos response")
    ap.add_argument("--strategy", default="midrange"); ap.add_argument("--bracket", type=int)
    ap.add_argument("--budget", type=float); ap.add_argument("--protect", action="append", default=[])
    ap.add_argument("--max-swaps", type=int, default=10)
    ap.add_argument("--extra-candidates", help="JSON list of card names to consider as adds")
    ap.add_argument("--edhrec-json", help="saved EDHREC data (browser snippet edhrec_candidates.js)")
    ap.add_argument("--candidates-json", help="supplied candidate cards (browser snippet scryfall_search.js)")
    ap.add_argument("--offline", action="store_true", help="phase2: don't attempt live EDHREC/Scryfall")
    ap.add_argument("--collection", help="phase2, optional: the user's collection (CSV export or text list)")
    ap.add_argument("--collection-mode", choices=["prefer", "only"], default="prefer")
    ap.add_argument("--collection-cards", help="phase2: card data for owned cards (browser snippet collection_cards.js)")
    a = ap.parse_args()
    py = sys.executable
    sk = find_skills(a.skills_dir)
    w = Path(a.work); w.mkdir(parents=True, exist_ok=True)
    I, S, C, X = sk["edh-deck-intake"], sk["edh-deck-structure"], sk["edh-combo-finder"], sk["edh-cut-add"]

    if a.phase == "phase1":
        if not (a.deck or a.parsed_json):
            sys.exit("phase1 needs --deck (file or URL) or --parsed-json")
        if a.cards_file:
            run([py, I / "scryfall_data.py", "update", "--cards-file", a.cards_file]
                + (["--tags-file", a.tags_file] if a.tags_file else []))
        elif not a.cards_json:
            run([py, I / "scryfall_data.py", "update"], allow_fail=True)  # falls back to API lookups
        cmd_extra = sum((["--commander", c] for c in a.commander or []), [])
        if a.parsed_json:
            Path(w / "parsed.json").write_text(Path(a.parsed_json).read_text(encoding="utf-8"), encoding="utf-8")
        elif a.deck.startswith("http"):
            if run([py, I / "fetch_deck_url.py", a.deck, "-o", w / "parsed.json"], allow_fail=True):
                sys.exit("\nCould not fetch the deck from its URL (private deck, site change, or the sandbox blocks the "
                         "site).\nEither ask the user to paste the export text and rerun with --deck deck.txt, or open "
                         "the deck page in a browser, run edh-deck-intake/scripts/browser/moxfield_deck.js there, join "
                         "the chunks into parsed.json and rerun with --parsed-json parsed.json "
                         "(see edh-deck-intake/references/browser_fetch.md).")
        else:
            run([py, I / "parse_decklist.py", a.deck, "-o", w / "parsed.json"] + cmd_extra)
        run([py, I / "enrich.py", w / "parsed.json", "-o", w / "deck.json"]
            + (["--cards-json", a.cards_json, "--no-api"] if a.cards_json else []))
        run([py, S / "tag_roles.py", w / "deck.json", "-o", w / "roles.json"])
        combo_cmd = [py, C / "find_combos.py", w / "deck.json", "--roles", w / "roles.json",
                     "-o", w / "combos.json", "--md", w / "combos.md"]
        if a.spellbook_response:
            combo_cmd += ["--response", a.spellbook_response]
        if run(combo_cmd, allow_fail=True):
            print("NOTE: combo lookup failed. Fetch it with edh-combo-finder/scripts/browser/combos_spellbook.js and rerun "
                  "phase1 with --spellbook-response, or continue without combos.json and say so in the report.",
                  file=sys.stderr)
        print(f"\nPhase 1 done. Next: review {w / 'roles.json'} ['needs_review'], write {w / 'overrides.json'}, "
              "then run phase2.", file=sys.stderr)
        return

    combos = w / "combos.json"
    ov = w / "overrides.json"
    br = ["--bracket", str(a.bracket)] if a.bracket else []
    run([py, S / "mana_analysis.py", w / "deck.json", w / "roles.json", "-o", w / "mana.json", "--strategy", a.strategy]
        + (["--overrides", ov] if ov.exists() else []) + br)
    run([py, S / "structure_report.py", w / "deck.json", w / "roles.json", w / "mana.json",
         "--strategy", a.strategy, "-o", w / "structure.json", "--md", w / "structure.md"]
        + (["--overrides", ov] if ov.exists() else []) + br)
    run([py, HERE / "bracket_floor.py", w / "deck.json", w / "structure.json", "-o", w / "bracket.json"]
        + (["--combos", combos] if combos.exists() else []))
    run([py, X / "candidates.py", w / "deck.json", w / "structure.json", "-o", w / "candidates.json",
         "--strategy", a.strategy]
        + (["--combos", combos] if combos.exists() else []) + br
        + (["--edhrec-json", a.edhrec_json] if a.edhrec_json else [])
        + (["--candidates-json", a.candidates_json] if a.candidates_json else [])
        + (["--offline"] if a.offline else [])
        + (["--collection", a.collection, "--collection-mode", a.collection_mode] if a.collection else [])
        + (["--collection-cards", a.collection_cards] if a.collection_cards else [])
        + (["--budget", str(a.budget)] if a.budget is not None else [])
        + (["--extra", a.extra_candidates] if a.extra_candidates else []))
    run([py, X / "score_swaps.py", w / "deck.json", w / "structure.json", w / "candidates.json",
         "-o", w / "swaps.json", "--md", w / "swaps.md", "--max-swaps", str(a.max_swaps)]
        + (["--combos", combos] if combos.exists() else []) + br
        + sum((["--protect", p] for p in a.protect), []))
    print(f"\nPhase 2 done. Inputs for the report are in {w}.", file=sys.stderr)


if __name__ == "__main__":
    main()
