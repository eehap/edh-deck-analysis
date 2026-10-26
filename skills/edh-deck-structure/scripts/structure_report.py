#!/usr/bin/env python3
"""Combine role tags (+ model overrides), targets and mana analysis into structure.json / structure.md.

Usage:
  python structure_report.py deck.json roles.json mana.json \
      [--overrides overrides.json] [--strategy polymorph] [--bracket 3] \
      [-o structure.json] [--md structure.md]

overrides.json (written by the model after reviewing roles.json["needs_review"]):
  {"Viscera Seer": {"roles": {"engine": 1.0}, "note": "free sac outlet, core to Meren"},
   "Darksteel Colossus": {"roles": {}, "note": "no synergy with Meren; off-plan"},
   "Serra's Emissary": {"cheated": true, "note": "polymorph target, rarely cast"},
   "Martial Coup": {"x_value": 5}}
"roles" REPLACES that card's roles (source="model"; the land role is kept). "flags_add"/"flags_remove"
adjust flags. "cheated" and "x_value" are read by mana_analysis.py; pass the same file to both.
Flags that depend on roles (symmetrical_wipe) are recomputed AFTER overrides are applied.

Also reports HIT DENSITY for every reveal-until effect (Polymorph, Mass Polymorph, Jace's -3, ...):
how many cards in the 99 it can hit (creature-only vs creature-or-planeswalker) and their average MV.
"""
from __future__ import annotations

import argparse
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from edh_common import card_type_line, dump_json, load_json  # noqa: E402

HERE = os.path.dirname(__file__)
ROLE_ORDER = ["land", "ramp", "card_advantage", "targeted_interaction", "mass_interaction",
              "protection", "tutor", "wincon", "recursion", "engine", "tokens"]
LABEL = {"land": "Lands", "ramp": "Ramp", "card_advantage": "Card advantage",
         "targeted_interaction": "Targeted interaction", "mass_interaction": "Mass interaction",
         "protection": "Protection", "tutor": "Tutors", "wincon": "Win conditions",
         "recursion": "Recursion", "engine": "Engine / synergy", "tokens": "Token makers (fodder)"}


def resolve_targets(strategy: str, bracket: int | None, karsten: float) -> dict:
    cfg = load_json(os.path.join(HERE, "targets.json"))
    if strategy not in cfg["strategies"]:
        raise SystemExit(f"Unknown strategy {strategy!r}; choose from {', '.join(cfg['strategies'])}")
    t = {k: v for k, v in copy.deepcopy(cfg["default"]).items() if not k.startswith("_")}
    curve_cap = cfg["default"].get("_curve_7plus_max", 6)
    for role, v in cfg["strategies"][strategy].items():
        if role == "_curve_7plus_max":
            curve_cap = v
        elif not role.startswith("_"):
            t[role] = copy.deepcopy(v)
    for role, d in cfg["bracket_offsets"].get(str(bracket), {}).items():
        if role.startswith("_") or role not in t:
            continue
        t[role]["min"] += d.get("min_delta", 0)
        t[role]["max"] += d.get("max_delta", 0)
        if isinstance(t[role]["target"], (int, float)):
            t[role]["target"] += round((d.get("min_delta", 0) + d.get("max_delta", 0)) / 2)
    lt = t["land"]["target"]
    if isinstance(lt, str):
        extra = int(lt.split("+")[1]) if "+" in lt else 0
        t["land"]["target"] = round(karsten + extra, 1)
    notes = [cfg["strategies"][strategy].get("_note"), cfg["bracket_offsets"].get(str(bracket), {}).get("_note")]
    return {"roles": t, "notes": [n for n in notes if n], "version": cfg["version"], "curve_7plus_max": curve_cap}


def _front_type(card: dict) -> str:
    faces = card.get("card_faces") or []
    if faces and card.get("layout") in ("modal_dfc", "transform"):
        return faces[0].get("type_line", "")
    return card_type_line(card).split(" // ")[0]


def hit_density(deck: dict, cards: list[dict]) -> list[dict]:
    """For each reveal-until effect: eligible hits in the 99 and their average MV."""
    main = [e for e in deck["cards"] if e["board"] == "main"]

    def pool(types):
        hits = [e for e in main if any(t in _front_type(e["card"]) for t in types)]
        n = sum(e["qty"] for e in hits)
        avg = sum(e["card"].get("cmc", 0) * e["qty"] for e in hits) / n if n else 0
        return n, round(avg, 2), sorted(e["name"] for e in hits)

    out = []
    cre = pool(("Creature",))
    cpw = pool(("Creature", "Planeswalker"))
    for c in cards:
        f = set(c.get("flags", []))
        if "reveal_until_creature_or_pw" in f:
            n, avg, names = cpw
            kind = "creature or planeswalker"
        elif "reveal_until_creature" in f:
            n, avg, names = cre
            kind = "creature"
        else:
            continue
        out.append({"effect": c["name"], "hits": kind, "eligible_cards": n, "avg_mv": avg,
                    "polymorph": "polymorph" in f})
    pools = {"creature": {"count": cre[0], "avg_mv": cre[1], "cards": cre[2]},
             "creature_or_planeswalker": {"count": cpw[0], "avg_mv": cpw[1], "cards": cpw[2]}}
    return out, pools


def build(deck, roles, mana, overrides=None, strategy="midrange", bracket=None):
    overrides = overrides or {}
    cards = copy.deepcopy(roles["cards"])
    applied, unknown = [], []
    by_name = {c["name"]: c for c in cards}
    for name, ov in overrides.items():
        c = by_name.get(name) or next((x for x in cards if x["name"].split(" // ")[0] == name), None)
        if not c:
            unknown.append(name)
            continue
        if "roles" in ov:
            keep_land = {"land": c["roles"]["land"]} if "land" in c["roles"] else {}
            c["roles"] = {**keep_land, **{r: {"weight": float(w), "confidence": "model", "source": "model"}
                                          for r, w in ov["roles"].items()}}
        fl = set(c.get("flags", [])) | set(ov.get("flags_add", []))
        fl -= set(ov.get("flags_remove", []))
        c["flags"] = sorted(fl)
        if ov.get("note"):
            c["model_note"] = ov["note"]
        c.pop("needs_review", None)
        applied.append(name)

    # flags that depend on roles are recomputed after overrides
    cheated = set(mana.get("cheated_cards", []))
    for c in cards:
        fl = set(c.get("flags", []))
        if "mass_interaction" not in c["roles"]:
            fl.discard("symmetrical_wipe")
        c["flags"] = sorted(fl)
        if c["name"] in cheated:
            c["cheated"] = True

    totals = {r: 0.0 for r in ROLE_ORDER}
    for c in cards:
        if c["board"] != "main":
            continue
        for r, v in c["roles"].items():
            if r in totals:
                totals[r] += v["weight"] * c["qty"]
    totals["land"] = mana["land_count"]

    tg = resolve_targets(strategy, bracket, mana["karsten_recommended_lands"])
    rows = []
    for r in ROLE_ORDER:
        have = round(totals[r], 2)
        t = tg["roles"].get(r)
        if not t:
            rows.append({"role": r, "have": have, "target": None, "min": None, "max": None, "status": "info"})
            continue
        status = "low" if have < t["min"] else "high" if have > t["max"] else "ok"
        rows.append({"role": r, "have": have, "target": t["target"], "min": t["min"], "max": t["max"],
                     "status": status,
                     "gap_to_target": round(have - (t["target"] if isinstance(t["target"], (int, float)) else have), 2)})

    sevens = mana["curve"].get("7+", 0)
    curve_note = None
    if sevens > tg["curve_7plus_max"]:
        curve_note = (f"{sevens} nonland cards cost 7+ (profile tolerates {tg['curve_7plus_max']}). "
                      + ("Fine if they are mostly cheated in." if cheated else "That is top-heavy for hard-casting."))

    unassigned = [c["name"] for c in cards if c["board"] == "main" and not c["roles"]]
    review_left = [c["name"] for c in cards if c.get("needs_review")]
    flags = {}
    for c in cards:
        for f in c.get("flags", []):
            if f in ("game_changer", "mld", "extra_turn", "stax", "symmetrical_wipe", "pillow_fort", "polymorph"):
                flags.setdefault(f, []).append(c["name"])
    density, pools = hit_density(deck, cards)

    return {
        "schema": "edh-structure/1",
        "commanders": deck.get("commanders", []),
        "color_identity": deck.get("color_identity", ""),
        "strategy_profile": strategy,
        "bracket_assumed": bracket,
        "targets_version": tg["version"],
        "profile_notes": tg["notes"],
        "role_table": rows,
        "curve_note": curve_note,
        "hit_density": density,
        "hit_pools": pools,
        "cheated_cards": sorted(cheated),
        "cards": cards,
        "unassigned_cards": unassigned,
        "still_needs_review": review_left,
        "overrides_applied": applied,
        "overrides_unknown_names": unknown,
        "flags": flags,
        "mana": mana,
    }


def to_markdown(s: dict) -> str:
    m = s["mana"]
    L = [f"## Structure — {' & '.join(s['commanders'])} [{s['color_identity'] or 'C'}]",
         f"Profile: **{s['strategy_profile']}**" + (f", Bracket {s['bracket_assumed']}" if s["bracket_assumed"] else "") +
         f" (targets v{s['targets_version']}; weighted counts, cards can fill several roles)", ""]
    L += ["| Role | Have | Target | Range | Status |", "|---|---|---|---|---|"]
    icon = {"ok": "OK", "low": "LOW", "high": "HIGH", "info": "-"}
    for r in s["role_table"]:
        rng = f"{r['min']}–{r['max']}" if r["min"] is not None else "-"
        L.append(f"| {LABEL[r['role']]} | {r['have']:g} | {r['target'] if r['target'] is not None else '-'} | {rng} | {icon[r['status']]} |")
    if s["profile_notes"]:
        L += [""] + [f"_{n}_" for n in s["profile_notes"]]
    if s["hit_density"]:
        L += ["", "### Hit density (reveal-until effects)",
              "| Effect | Can hit | Eligible cards in the 99 | Avg MV of hits |", "|---|---|---|---|"]
        for h in s["hit_density"]:
            L.append(f"| {h['effect']} | {h['hits']} | {h['eligible_cards']} | {h['avg_mv']} |")
        p = s["hit_pools"]
        L.append(f"\nCreature hits: {p['creature']['count']} · creature-or-planeswalker hits: "
                 f"{p['creature_or_planeswalker']['count']}. Fewer hits means each effect digs deeper and mills/bottoms more.")
    L += ["", "### Mana",
          f"- Lands: **{m['land_count']:g}** (MDFCs fractional). Karsten's formula: **{m['karsten_recommended_lands']}** "
          f"(avg MV {m['avg_mv']}, {m['cheap_ramp_draw']} cheap ramp/draw). EDHREC average: ~{m['edhrec_average_lands']}.",
          f"- Always-tapped lands ({m['tapped_lands']}): {', '.join(m.get('tapped_land_names', [])) or 'none'}.",
          f"- Conditionally untapped ({m['conditional_untapped_lands']}): {', '.join(m.get('conditional_land_names', [])) or 'none'}.",
          f"- Average land quality {m['land_quality_avg']}/1.0. Curve (nonland, printed MV): "
          + " · ".join(f"{k}: {v}" for k, v in m["curve"].items())]
    if s.get("curve_note"):
        L.append(f"- {s['curve_note']}")
    if m.get("x_spells"):
        L.append("- X spells judged at: " + ", ".join(f"{x['card']} X={x['judged_at_x']} (MV {x['effective_mv']:g})" for x in m["x_spells"]))
    if m.get("cheated_cards"):
        L.append(f"- Excluded from colour requirements as cheated into play ({len(m['cheated_cards'])}): "
                 + ", ".join(m["cheated_cards"]))
    if len(s["color_identity"]) >= 4 and m.get("hardest_to_cast"):
        L.append("- Hardest to cast on curve: " + "; ".join(
            f"{r['card']} {r['cost']} ({r['color']} {r['sources_at_mv']:g}/{r['required']})" for r in m["hardest_to_cast"][:8]))
    else:
        for col, d in m["per_color"].items():
            h = d["hardest_card"]
            if h:
                ok = "OK" if h["deficit"] <= 0.5 else f"short by {h['deficit']:g}"
                L.append(f"- {col}: {d['pips']} pips; hardest card {h['card']} {h['cost']} needs {h['required']} "
                         f"sources, has {h['sources_at_mv']:g} → {ok}")
    if m["recommendations"] or m["warnings"]:
        L += [""] + [f"- ⚠ {w}" for w in m["warnings"]] + [f"- → {r}" for r in m["recommendations"]]
    if s["flags"]:
        L += ["", "### Flags"]
        for f, names in s["flags"].items():
            L.append(f"- {f.replace('_', ' ')} ({len(names)}): {', '.join(names)}")
    if s["unassigned_cards"]:
        L += ["", f"### No role assigned ({len(s['unassigned_cards'])})", ", ".join(s["unassigned_cards"])]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck"); ap.add_argument("roles"); ap.add_argument("mana")
    ap.add_argument("--overrides")
    ap.add_argument("--strategy", default="midrange")
    ap.add_argument("--bracket", type=int)
    ap.add_argument("-o", "--out", default="structure.json")
    ap.add_argument("--md")
    a = ap.parse_args()
    s = build(load_json(a.deck), load_json(a.roles), load_json(a.mana),
              load_json(a.overrides) if a.overrides else None, a.strategy, a.bracket)
    dump_json(s, a.out)
    md = to_markdown(s)
    if a.md:
        open(a.md, "w").write(md)
    print(md, file=sys.stderr)
    if s["still_needs_review"]:
        print(f"NOTE: {len(s['still_needs_review'])} card(s) still need review: {', '.join(s['still_needs_review'])}",
              file=sys.stderr)
    if s["overrides_unknown_names"]:
        print(f"WARNING: overrides for unknown cards: {s['overrides_unknown_names']}", file=sys.stderr)


if __name__ == "__main__":
    main()
