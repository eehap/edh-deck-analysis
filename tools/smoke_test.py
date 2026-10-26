#!/usr/bin/env python3
"""Offline end-to-end test: run the whole pipeline on the synthetic Meren deck in dev/fixtures/.

Needs no network. It checks the numbers the fixture is built to produce, so a change that breaks
parsing, role tagging, mana math, combo scoring, bracket rules or swaps shows up here.

Usage:  python tools/smoke_test.py   (exit 0 = all checks passed)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FX = ROOT / "dev" / "fixtures"
PIPE = ROOT / "skills" / "edh-deck-review" / "scripts" / "pipeline.py"

OVERRIDES = {
    "Viscera Seer": {"roles": {"engine": 1.0}}, "Ashnod's Altar": {"roles": {"engine": 1.0, "ramp": 0.25}},
    "Phyrexian Altar": {"roles": {"engine": 1.0, "ramp": 0.25}}, "Blood Artist": {"roles": {"engine": 1.0, "wincon": 0.5}},
    "Zulaport Cutthroat": {"roles": {"engine": 1.0, "wincon": 0.5}},
    "Mikaeus, the Unhallowed": {"roles": {"engine": 1.0, "wincon": 1.0}}, "Triskelion": {"roles": {"wincon": 1.0}},
    "Gravecrawler": {"roles": {"engine": 1.0}}, "Spore Frog": {"roles": {"protection": 0.5, "engine": 0.5}},
    "Pelakka Wurm": {"roles": {"card_advantage": 0.25}},
    "Darksteel Colossus": {"roles": {}, "note": "off-plan: never dies, so no Meren value"},
}


def run(args: list, env: dict) -> None:
    r = subprocess.run([sys.executable, str(PIPE), *map(str, args)], env=env, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
        sys.exit(f"pipeline failed: {' '.join(map(str, args[:3]))}")


def main() -> None:
    fails = []

    def check(cond, what):
        print(("PASS " if cond else "FAIL ") + what)
        if not cond:
            fails.append(what)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        env = {**os.environ, "EDH_CACHE_DIR": str(tmp / "cache")}
        w = tmp / "work"
        run(["phase1", "--work", w, "--deck", FX / "meren.txt", "--cards-file", FX / "oracle-cards.json",
             "--tags-file", FX / "oracle-tags.json", "--spellbook-response", FX / "spellbook_meren.json"], env)
        (w / "overrides.json").write_text(json.dumps(OVERRIDES))
        (w / "extra.json").write_text(json.dumps(["Fatal Push", "Deadly Rollick", "Rampant Growth"]))
        run(["phase2", "--work", w, "--strategy", "aristocrats", "--bracket", "3", "--budget", "10", "--offline",
             "--extra-candidates", w / "extra.json", "--collection", FX / "meren_collection.csv"], env)

        load = lambda n: json.loads((w / n).read_text())  # noqa: E731
        deck, roles, combos = load("deck.json"), load("roles.json"), load("combos.json")
        mana, br, swaps, cands = load("mana.json"), load("bracket.json"), load("swaps.json"), load("candidates.json")

        check(deck["counts"]["main_and_commander"] == 100 and not deck["unresolved"], "intake: 100 cards, 0 unresolved")
        check(deck["color_identity"] == "BG", "intake: identity BG")
        check(len(roles["needs_review"]) == 11, f"tagging: 11 cards need review (got {len(roles['needs_review'])})")
        check(all(c["game_winning"] for c in combos["included"]) and len(combos["included"]) == 2,
              "combos: 2 complete, both game-winning")
        check(mana["per_color"]["B"]["hardest_card"]["card"] == "Sign in Blood", "mana: Sign in Blood is the hardest black card")
        check(br["floor"] == 3, "bracket: rules floor 3 (three Game Changers)")
        pairs = [(s["cut"], s["add"]) for s in swaps["swaps"]]
        check(("Darksteel Colossus", "Nim Deathmantle") in pairs, "swaps: Darksteel Colossus -> Nim Deathmantle")
        check(all(s["add_owned"] for s in swaps["swaps"] if s["add"] in ("Nim Deathmantle", "Fatal Push")),
              "collection: owned adds marked owned")
        names = {c["name"] for c in cands["candidates"]}
        check(not names & {"Armageddon", "Time Warp"}, "collection: off-identity owned cards filtered out")

    print(f"\n{'all checks passed' if not fails else f'{len(fails)} check(s) failed'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
