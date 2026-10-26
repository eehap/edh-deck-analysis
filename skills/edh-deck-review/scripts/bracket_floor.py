#!/usr/bin/env python3
"""Minimum bracket by the official rules (hard floor), plus evidence for the model's own estimate.

Hard rules checked (Commander Brackets beta; see bracket_rules.json for dates):
  Game Changers: 0 -> B1/B2 possible; 1-3 -> at least B3; 4+ -> at least B4
  Mass land denial -> at least B4
  Extra turns: one card is fine; 2+ extra-turn cards or extra turns + recursion -> possible chaining (B4 unless proven otherwise)
  Two-card combos: any -> at least B3 (B2 has no intentional ones); assemblable before turn 6 -> at least B4
Optionally asks Commander Spellbook's /estimate-bracket/ (schema not verified; result stored raw).

The floor is "minimum bracket by rules". Intent, speed and the table's expectations are a
separate judgment the report must label as such.

Usage: python bracket_floor.py deck.json structure.json [--combos combos.json] [--spellbook] [-o bracket.json]
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
from edh_common import NetworkUnavailable, dump_json, http, load_json, norm_name  # noqa: E402


def floor(deck: dict, structure: dict, combos: dict | None, use_spellbook: bool = False) -> dict:
    rules = load_json(os.path.join(HERE, "bracket_rules.json"))
    gc_names = {norm_name(n) for n in rules["game_changers"]}
    in_deck = [c for c in deck["cards"] if c["board"] in ("main", "commander")]
    gcs = []
    for c in in_deck:
        flag = c["card"].get("game_changer")
        if flag is True or (flag is None and norm_name(c["name"]) in gc_names):
            gcs.append(c["name"])
    flags = structure.get("flags", {})
    mld = flags.get("mld", [])
    extra = flags.get("extra_turn", [])
    recursion = [c["name"] for c in structure.get("cards", []) if "recursion" in c.get("roles", {})]

    reasons, level = [], 1
    def bump(n, why):
        nonlocal level
        reasons.append({"min_bracket": n, "why": why})
        level = max(level, n)

    if gcs:
        bump(3 if len(gcs) <= 3 else 4, f"{len(gcs)} Game Changer(s): {', '.join(gcs)}")
    if mld:
        bump(4, f"mass land denial: {', '.join(mld)}")
    if len(extra) >= 2:
        bump(4, f"{len(extra)} extra-turn cards ({', '.join(extra)}) can chain; Brackets 1-3 forbid chaining")
    elif extra and recursion:
        reasons.append({"min_bracket": None, "why": f"extra turns ({', '.join(extra)}) plus recursion: check it can't loop"})
    elif extra:
        reasons.append({"min_bracket": None, "why": f"one extra-turn card ({', '.join(extra)}); fine if it can't chain"})

    two_card = []
    if combos:
        for c in combos.get("included", []):
            if len(c["pieces"]) <= 2 and not c.get("templates_required"):
                early = c.get("robustness", {}).get("early_two_card", False)
                two_card.append({"combo": " + ".join(c["pieces"]), "early": early,
                                 "total_mv": c.get("robustness", {}).get("total_mv"), "bracket_tag": c.get("bracket_tag")})
                bump(4 if early else 3, f"two-card combo {' + '.join(c['pieces'])}"
                     + (" can come together before turn 6" if early else " (late enough for Bracket 3)"))
    elif combos is None:
        reasons.append({"min_bracket": None, "why": "combo check not run; two-card combos unknown"})

    # Judgment input from Commander Spellbook (not a hard floor change): combo bracket tags, combos that
    # produce Mass Land Denial, and Spellbook's deck-level estimate.
    judgment = []
    if combos:
        for c in combos.get("included", []):
            tag = c.get("bracket_tag_name") or c.get("bracket_tag")
            if tag:
                judgment.append(f"Spellbook tags {' + '.join(c['pieces'])} as {tag}"
                                + (" and it produces Mass Land Denial" if c.get("mass_land_denial") else ""))
            elif c.get("mass_land_denial"):
                judgment.append(f"{' + '.join(c['pieces'])} produces Mass Land Denial")
        est = combos.get("spellbook_estimate") or {}
        if est.get("bracketTag"):
            judgment.append(f"Spellbook's deck-level tag: {est.get('bracketTag_name') or est['bracketTag']} "
                            "(Spellbook's own scale: Exhibition, Core, Oddball, Powerful, Spicy, Ruthless, Banned; the "
                            "names track how competitive the combos are, but the mapping to official bracket numbers "
                            "isn't documented, so don't quote it as a bracket)")
        if combos.get("mass_land_denial_combos"):
            judgment.append("A combo that ends in mass land denial is closer to Bracket 4 in spirit, even though the "
                            "rules floor only counts MLD cards; say so in the estimate.")

    if level == 1:
        if judgment:
            why = ("no Game Changers, MLD cards, chained extra turns or two-card combos, so the hard rules set no "
                   "floor above 1 - but the combos below are judgment input that can place the deck much higher; "
                   "don't read this floor as the deck's bracket")
        else:
            why = ("no Game Changers, MLD, chained extra turns or two-card combos; "
                   "Bracket 1 vs 2 depends on theme and intent")
        reasons.append({"min_bracket": 1, "why": why})
    sb = None
    if use_spellbook:
        body = {"commanders": [{"card": c["name"], "quantity": 1} for c in in_deck if c["board"] == "commander"],
                "main": [{"card": c["name"], "quantity": c["qty"]} for c in in_deck if c["board"] == "main"]}
        try:
            sb = http("https://backend.commanderspellbook.com/estimate-bracket/", method="POST", body=body)
        except (NetworkUnavailable, Exception) as e:  # schema unverified
            sb = {"error": f"{type(e).__name__}: {e}"}

    return {"schema": "edh-bracket/1", "rules_verified_through": rules["verified_through"],
            "floor": level, "floor_name": rules["brackets"][str(level)]["name"],
            "game_changers": gcs, "mld": mld, "extra_turns": extra, "two_card_combos": two_card,
            "reasons": reasons, "judgment_inputs": judgment, "spellbook_estimate_raw": sb,
            "model_estimate_prompt": "Now judge speed and intent separately: how fast can the deck win or lock "
                                     "the game (compare with the bracket turn expectations: B1 9+, B2 8+, B3 6+, "
                                     "B4 4+ turns), how much fast mana and tutoring it has, and what the user said "
                                     "they want. Report this as a model estimate, distinct from the rules floor."}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck"); ap.add_argument("structure")
    ap.add_argument("--combos")
    ap.add_argument("--spellbook", action="store_true")
    ap.add_argument("-o", "--out", default="bracket.json")
    a = ap.parse_args()
    res = floor(load_json(a.deck), load_json(a.structure), load_json(a.combos) if a.combos else None, a.spellbook)
    dump_json(res, a.out)
    print(f"Minimum bracket by rules: {res['floor']} ({res['floor_name']})", file=sys.stderr)
    for r in res["reasons"]:
        print(f"  - {r['why']}", file=sys.stderr)
    if res["judgment_inputs"]:
        print("Judgment inputs (not part of the floor):", file=sys.stderr)
        for j in res["judgment_inputs"]:
            print(f"  * {j}", file=sys.stderr)


if __name__ == "__main__":
    main()
