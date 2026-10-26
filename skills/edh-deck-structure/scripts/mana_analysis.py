#!/usr/bin/env python3
"""Mana base analysis for a 99-card Commander deck, following Frank Karsten.

1. Land count: lands = 31.42 + 3.13 * avgMV - 0.28 * cheap_ramp_draw
   (Karsten, "How Many Lands Do You Need in Your Deck? An Updated Analysis", TCGplayer).
   avgMV is over nonland cards in the 99 (MDFC land/spell counted by front face; commander excluded).
   "Cheap" defaults to MV <= 3 ramp/draw pieces (FreeMully's reading); --cheap-mv 2 for a stricter one.
2. Colored sources: Karsten 2022 99-card table (90% for 1-drops, +1 pp per turn, conditioned on
   hitting land drops; 41-land deck; free mulligan + Commander draw modelled).
   Most demanding card per color sets the requirement; gold cards add 1.
   Fractional sources: rocks 0.75 (MV>=3 only), dorks 0.5 (MV>=2 only), 2-MV land ramp 0.75 (MV>=3),
   3-MV land ramp 0.5 (MV>=4), MDFC land 0.8 (mythic 1.0), Fabled-Passage-style basic fetchers 1.0
   in two-color decks / 0.67 in 3+, Exotic Orchard 0.75, tapped lands don't count for 1-drops.
3. Land quality, tapped count, colorless-land share, curve; the tapped and conditional lands are named.
4. X spells are judged at a sensible X, not their printed MV ({X}{W}{W} Martial Coup is not a two-drop):
   the X in "if X is N or more" when printed, otherwise X=3; set "x_value" per card in overrides.json.
5. Cheated cards - ones the deck mostly puts into play without casting (polymorph and reveal-until hits,
   reanimation targets, sneak-in effects) - don't drive colour requirements. Mark them in overrides.json
   ({"Serra's Emissary": {"cheated": true}}). When the deck has 3+ cheat effects, big creatures (and
   planeswalkers, if an effect can hit them) are suggested; with --strategy polymorph/cheat/reanimator the
   suggestions are applied unless an override says "cheated": false.
6. Four- and five-colour decks can't reach Karsten's ~30 sources for a cheap double pip, so they get a
   ranking of the hardest cards to cast on curve instead of "raise X sources by ~10".

Usage: python mana_analysis.py deck.json roles.json [-o mana.json] [--bracket 3] [--cheap-mv 3]
                               [--overrides overrides.json] [--strategy polymorph]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from edh_common import card_text, card_type_line, dump_json, load_json  # noqa: E402

COLORS = "WUBRG"
BASIC_OF = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}

# Karsten 2022, 99-card decks. key = (generic, colored pips of that color)
KARSTEN = {
    (0, 1): 19, (1, 1): 19, (2, 1): 18, (3, 1): 16, (4, 1): 15, (5, 1): 14,
    (0, 2): 30, (1, 2): 28, (2, 2): 26, (3, 2): 23, (4, 2): 22, (5, 2): 20,
    (0, 3): 36, (1, 3): 33, (2, 3): 30, (3, 3): 28, (4, 3): 26,
    (0, 4): 39, (1, 4): 36,
}
MAX_GENERIC = {1: 5, 2: 5, 3: 4, 4: 1}
EDHREC_AVG_LANDS = 36  # CoolStuffInc citing EDHREC, Apr 2026


def required_sources(generic: int, pips: int, gold: bool) -> int:
    p = min(pips, 4)
    g = min(max(generic, 0), MAX_GENERIC[p])
    req = KARSTEN[(g, p)]
    return req + (1 if gold else 0)


def pips_in(cost: str) -> Counter:
    c = Counter()
    for sym in re.findall(r"\{([^}]+)\}", cost or ""):
        parts = sym.split("/")
        cols = [x for x in parts if x in COLORS]
        if not cols:
            continue
        for x in cols:  # hybrid and Phyrexian pips count for each color they can pay
            c[x] += 1
    return c


def spell_cost(card: dict) -> tuple[str, float]:
    faces = card.get("card_faces") or []
    if faces and card.get("layout") in ("modal_dfc", "transform", "flip", "adventure", "split"):
        if card.get("layout") in ("split", "adventure"):
            costs = [f.get("mana_cost", "") for f in faces]
            return max(costs, key=lambda s: sum(pips_in(s).values())), card.get("cmc", 0)
        return faces[0].get("mana_cost", ""), card.get("cmc", 0)
    return card.get("mana_cost", ""), card.get("cmc", 0)


def front_type(card: dict) -> str:
    faces = card.get("card_faces") or []
    if faces and card.get("layout") in ("modal_dfc", "transform"):
        return faces[0].get("type_line", "")
    return card_type_line(card).split(" // ")[0]


def land_profile(card: dict, identity: str, basics_in_deck: set[str], n_colors: int) -> dict:
    """Colors a land (or MDFC land face) provides, with weights, tapped status and quality."""
    text = card_text(card)
    tl = card_type_line(card)
    faces = card.get("card_faces") or []
    mdfc = card.get("layout") == "modal_dfc" and "Land" not in front_type(card)
    if mdfc:
        land_face = next((f for f in faces if "Land" in f.get("type_line", "")), {})
        text = land_face.get("oracle_text", "")
        tl = land_face.get("type_line", "")
    low = text.lower()
    colors: dict[str, float] = {}

    def give(cs, w):
        for c in cs:
            if c in identity:
                colors[c] = max(colors.get(c, 0), w)

    produced = [c for c in (card.get("produced_mana") or []) if c in COLORS]
    if "commander's color identity" in low or re.search(r"add one mana of any color", low):
        give(identity, 1.0)
    elif "could produce" in low:                       # Exotic Orchard style
        give(identity, 0.75)
    elif mdfc:
        give(re.findall(r"\{([WUBRG])\}", text), 1.0)
    else:
        give(produced, 1.0)
        for t, c in BASIC_OF.items():                   # typed duals/shocks
            if re.search(rf"\b{t}\b", tl):
                give(c, 1.0)
    fetched = re.search(r"search your library for an? ([^.]*?) card", text, re.I)
    if fetched and not colors:
        what = fetched.group(1)
        named = [BASIC_OF[t] for t in BASIC_OF if t in what]
        if named:
            give(named, 1.0)                            # true fetchland
        elif "basic land" in what:
            give([BASIC_OF[b] for b in basics_in_deck], 1.0 if n_colors <= 2 else 0.67)
    tapped = bool(re.search(r"enters (?:the battlefield )?tapped", low))
    conditional = tapped and bool(re.search(r"unless|if you don't|you may pay \d+ life", low))
    if "sacrifice" in low and "search your library" in low and re.search(r"put it onto the battlefield tapped", low):
        tapped = True
    if mdfc:
        w = 1.0 if card.get("rarity") == "mythic" else 0.8
        colors = {c: min(v, w) for c, v in colors.items()}
        if not re.search(r"pay \d+ life", low):
            tapped = tapped or "tapped" in low
    is_basic = "Basic" in tl
    ncol = sum(1 for v in colors.values() if v >= 0.67)
    if is_basic:
        quality = 1.0
    elif not colors:
        quality = 0.5
    elif tapped and not conditional:
        quality = 0.6 if ncol >= 2 else 0.5
        if re.search(r"cycling|scry", low):
            quality = 0.75
    elif conditional:
        quality = 0.8
    else:
        quality = 1.0 if ncol >= 2 or n_colors == 1 else 0.9
    return {"colors": colors, "tapped": tapped and not conditional, "conditional": conditional,
            "colorless_only": not colors, "quality": quality, "mdfc": mdfc,
            "land_weight": (1.0 if card.get("rarity") == "mythic" else 0.8) if mdfc else 1.0}


CHEAT_STRATEGIES = {"polymorph", "cheat", "reanimator"}
CHEAT_FLAGS = {"polymorph", "reveal_until", "cheat_into_play", "reanimation"}


def x_value(card: dict, override: dict | None = None) -> int:
    """The X a player realistically pays: the printed threshold ("If X is 5 or more"), else 3."""
    if override and override.get("x_value") is not None:
        return int(override["x_value"])
    m = re.search(r"if x is (\d+) or (?:more|greater)", card_text(card).lower())
    return int(m.group(1)) if m else 3


def effective_mv(card: dict, override: dict | None = None) -> tuple[float, int | None]:
    cost, cmc = spell_cost(card)
    xs = len(re.findall(r"\{X\}", cost or ""))
    if not xs:
        return cmc, None
    xv = x_value(card, override)
    return cmc + xs * xv, xv


def cheated_cards(deck: dict, roles: dict, overrides: dict, strategy: str) -> tuple[set, list, list]:
    """(applied, suggested, effects): cards whose pips shouldn't drive colour requirements."""
    flags_by = {c["name"]: set(c.get("flags", [])) for c in roles.get("cards", [])}
    effects = [n for n, f in flags_by.items() if f & CHEAT_FLAGS]
    pw_hits = any("reveal_until_creature_or_pw" in f for f in flags_by.values())
    suggested = []
    if len(effects) >= 3:
        for e in deck["cards"]:
            if e["board"] != "main":
                continue
            c = e["card"]
            ft = front_type(c)
            if not ("Creature" in ft or (pw_hits and "Planeswalker" in ft)):
                continue
            cost, cmc = spell_cost(c)
            heavy = max(pips_in(cost).values(), default=0)
            # creatures: MV 6+, or MV 5 with a triple pip; planeswalkers are usually cast, so only MV 6+
            if cmc >= 6 or ("Creature" in ft and cmc >= 5 and heavy >= 3):
                suggested.append(e["name"])
    applied = set(suggested) if strategy in CHEAT_STRATEGIES else set()
    for name, ov in (overrides or {}).items():
        if ov.get("cheated") is True:
            applied.add(name)
        elif ov.get("cheated") is False:
            applied.discard(name)
    return applied, suggested, effects


def analyze(deck: dict, roles: dict, bracket: int | None = None, cheap_mv: int = 3,
            overrides: dict | None = None, strategy: str = "midrange") -> dict:
    overrides = overrides or {}
    identity = deck.get("color_identity", "")
    n_colors = len(identity)
    role_by_name = {c["name"]: c for c in roles.get("cards", [])}
    main = [e for e in deck["cards"] if e["board"] == "main"]
    cmdrs = [e for e in deck["cards"] if e["board"] == "commander"]
    basics_in_deck = {t for e in main for t in BASIC_OF if "Basic" in card_type_line(e["card"]) and t in card_type_line(e["card"])}

    lands, spells = [], []
    for e in main:
        ft = front_type(e["card"])
        prof = None
        if "Land" in ft or (e["card"].get("layout") == "modal_dfc" and "Land" in card_type_line(e["card"])):
            prof = land_profile(e["card"], identity, basics_in_deck, n_colors)
            lands.append((e, prof))
        if "Land" not in ft:
            spells.append(e)

    land_count = sum(e["qty"] * p["land_weight"] for e, p in lands)
    land_count_physical = sum(e["qty"] for e, p in lands if not p["mdfc"])
    spell_qty = sum(e["qty"] for e in spells)
    avg_mv = sum(e["card"].get("cmc", 0) * e["qty"] for e in spells) / max(spell_qty, 1)

    cheap = 0
    for e in spells:
        r = role_by_name.get(e["name"], {}).get("roles", {})
        if e["card"].get("cmc", 0) <= cheap_mv and (
                r.get("ramp", {}).get("weight", 0) >= 0.5 or r.get("card_advantage", {}).get("weight", 0) >= 0.5):
            cheap += e["qty"]
    rec = 31.42 + 3.13 * avg_mv - 0.28 * cheap

    # nonland colored sources
    nonland_src = []  # (colors set, weight, min_mv)
    for e in spells:
        r = role_by_name.get(e["name"], {})
        ramp = r.get("roles", {}).get("ramp")
        if not ramp or ramp["weight"] < 1.0:
            continue
        c = e["card"]
        ft = front_type(c)
        text = card_text(c)
        prod = [x for x in (c.get("produced_mana") or []) if x in identity]
        if "commander's color identity" in text or "any color" in text:
            prod = list(identity)
        cmc = c.get("cmc", 0)
        if re.search(r"search your library for", text, re.I):
            fetch_cols = [BASIC_OF[t] for t in BASIC_OF if re.search(rf"\b{t}\b", text)] or \
                         [BASIC_OF[b] for b in basics_in_deck]
            fetch_cols = [x for x in fetch_cols if x in identity]
            if cmc <= 2:
                nonland_src.append((set(fetch_cols), 0.75, 3, e["name"]))
            else:
                nonland_src.append((set(fetch_cols), 0.5, 4, e["name"]))
        elif "Creature" in ft and prod:
            nonland_src.append((set(prod), 0.5, 2, e["name"]))
        elif "Artifact" in ft and prod:
            nonland_src.append((set(prod), 0.75, 3, e["name"]))

    def sources(color: str, mv: float) -> float:
        total = 0.0
        for e, p in lands:
            w = p["colors"].get(color, 0)
            if mv <= 1 and p["tapped"]:
                continue
            total += w * e["qty"]
        for cols, w, min_mv, _ in nonland_src:
            if color in cols and mv >= min_mv:
                total += w
        return round(total, 2)

    cheated, cheat_suggested, cheat_effects = cheated_cards(deck, roles, overrides, strategy)

    # requirements per color (cheated cards excluded; X spells at their effective MV)
    per_color, castability, x_spells = {}, {}, []
    for e in spells + cmdrs:
        if e["name"] in cheated:
            continue
        cost, _ = spell_cost(e["card"])
        mv, xv = effective_mv(e["card"], overrides.get(e["name"]))
        if xv is not None:
            x_spells.append({"card": e["name"], "cost": cost, "judged_at_x": xv, "effective_mv": mv})
        p = pips_in(cost)
        gold = len([x for x in p if p[x]]) > 1
        for col in identity:
            if not p.get(col):
                continue
            need = required_sources(int(round(mv)) - p[col], p[col], gold)
            have = sources(col, mv)
            row = {"card": e["name"], "cost": cost, "mv": mv, "color": col, "required": need,
                   "sources_at_mv": have, "deficit": round(need - have, 2), "ratio": round(have / need, 2)}
            d = per_color.setdefault(col, {"pips": 0, "hardest_card": None})
            d["pips"] += p[col] * e["qty"]
            if d["hardest_card"] is None or row["deficit"] > d["hardest_card"]["deficit"]:
                d["hardest_card"] = {k: row[k] for k in ("card", "cost", "mv", "required", "sources_at_mv", "deficit")}
            prev = castability.get(e["name"])
            if prev is None or row["ratio"] < prev["ratio"]:
                castability[e["name"]] = row
    for col in identity:
        d = per_color.setdefault(col, {"pips": 0, "hardest_card": None})
        d["land_sources"] = round(sources(col, 99) - sum(w for cols, w, _, _ in nonland_src if col in cols), 2)
        d["total_sources_mv5"] = sources(col, 5)
    hardest = sorted((r for r in castability.values() if r["deficit"] > 0.5), key=lambda r: (r["ratio"], -r["deficit"]))[:12]

    tapped_names = [e["name"] for e, p in lands if p["tapped"]]
    conditional_names = [e["name"] for e, p in lands if p["conditional"]]
    colorless_names = [e["name"] for e, p in lands if p["colorless_only"] and not p["mdfc"]]
    tapped = sum(e["qty"] for e, p in lands if p["tapped"])
    conditional = sum(e["qty"] for e, p in lands if p["conditional"])
    colorless_only = sum(e["qty"] for e, p in lands if p["colorless_only"] and not p["mdfc"])
    quality = sum(p["quality"] * e["qty"] for e, p in lands) / max(sum(e["qty"] for e, _ in lands), 1)

    curve = Counter()
    for e in spells:
        curve[min(int(e["card"].get("cmc", 0)), 7)] += e["qty"]

    warnings, recs = [], []
    diff = rec - land_count
    if diff >= 1.5:
        recs.append(f"Add about {round(diff)} land(s): Karsten's formula suggests {rec:.1f}, the deck has {land_count:g}.")
    elif diff <= -2:
        recs.append(f"Room to cut about {round(-diff)} land(s): formula {rec:.1f} vs {land_count:g} in the deck.")
    if n_colors >= 4:
        if hardest:
            warnings.append(f"{n_colors}-colour deck: Karsten's targets for cheap multi-pip costs (e.g. 30 sources for "
                            "a CC two-drop) aren't reachable, so these are ranked by how castable they are on curve.")
            recs.append("Hardest to cast on curve: " + "; ".join(
                f"{r['card']} {r['cost']} ({r['color']}: {r['sources_at_mv']:g}/{r['required']} sources)" for r in hardest[:6])
                + ". Treat the top of this list as late-game cards or cut candidates; when choosing lands, favour the "
                  "colours of your cheapest pips.")
    else:
        for col, d in per_color.items():
            h = d["hardest_card"]
            if h and h["deficit"] > 0.5:
                warnings.append(f"{col}: {h['card']} ({h['cost']}) wants {h['required']} sources by its turn; "
                                f"deck has {h['sources_at_mv']}.")
                recs.append(f"Raise {col} sources by ~{round(h['deficit'])} (swap basics for duals/fetches, or add "
                            f"{col}-producing rocks), or cut/replace {h['card']}.")
    if cheat_suggested and not cheated:
        recs.append(f"{len(cheat_effects)} cheat-into-play effects found; if these mostly arrive without being cast, "
                    "mark them \"cheated\" in overrides.json (or use --strategy polymorph): " + ", ".join(cheat_suggested))
    if bracket and bracket >= 3 and tapped > 6:
        warnings.append(f"{tapped} lands always enter tapped; more than 6 is slow for Bracket {bracket}.")
    if n_colors >= 3 and colorless_only > 0.1 * max(land_count_physical, 1):
        warnings.append(f"{colorless_only} colorless-only lands in a {n_colors}-color deck (over 10% of lands).")

    return {
        "schema": "edh-mana/1",
        "identity": identity,
        "land_count": round(land_count, 2),
        "land_count_physical": land_count_physical,
        "avg_mv": round(avg_mv, 2),
        "cheap_ramp_draw": cheap,
        "cheap_mv_cutoff": cheap_mv,
        "karsten_recommended_lands": round(rec, 1),
        "edhrec_average_lands": EDHREC_AVG_LANDS,
        "per_color": per_color,
        "nonland_sources": [{"name": n, "colors": "".join(sorted(c)), "weight": w, "counts_from_mv": m}
                            for c, w, m, n in nonland_src],
        "tapped_lands": tapped,
        "tapped_land_names": tapped_names,
        "conditional_untapped_lands": conditional,
        "conditional_land_names": conditional_names,
        "colorless_only_lands": colorless_only,
        "colorless_only_land_names": colorless_names,
        "hardest_to_cast": hardest,
        "x_spells": x_spells,
        "cheated_cards": sorted(cheated),
        "cheated_suggested": cheat_suggested,
        "cheat_effects": cheat_effects,
        "land_quality_avg": round(quality, 2),
        "curve": {("7+" if k == 7 else str(k)): curve[k] for k in range(8)},
        "warnings": warnings,
        "recommendations": recs,
        "assumptions": [
            "Karsten 99-card table assumes 41 lands and a London mulligan with the free Commander mulligan.",
            f"'Cheap' ramp/draw = MV <= {cheap_mv} with ramp or card-advantage weight >= 0.5.",
            "Hybrid/Phyrexian pips count toward every color they can pay.",
            "Commander's own cost is included in color requirements; it is excluded from avg MV.",
            "X spells are judged at their printed threshold X (or X=3); avg MV uses printed MV as Karsten does.",
            "Cheated cards (put into play without casting) are excluded from colour requirements.",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("roles")
    ap.add_argument("-o", "--out", default="mana.json")
    ap.add_argument("--bracket", type=int)
    ap.add_argument("--cheap-mv", type=int, default=3)
    ap.add_argument("--overrides", help="overrides.json (cheated / x_value per card)")
    ap.add_argument("--strategy", default="midrange")
    a = ap.parse_args()
    ov = load_json(a.overrides) if a.overrides and os.path.exists(a.overrides) else {}
    res = analyze(load_json(a.deck), load_json(a.roles), a.bracket, a.cheap_mv, ov, a.strategy)
    dump_json(res, a.out)
    print(f"Lands {res['land_count']:g} (Karsten {res['karsten_recommended_lands']}, EDHREC avg ~36); "
          f"avg MV {res['avg_mv']}; cheap ramp/draw {res['cheap_ramp_draw']}; tapped {res['tapped_lands']}",
          file=sys.stderr)
    for w in res["warnings"] + res["recommendations"]:
        print("  - " + w, file=sys.stderr)


if __name__ == "__main__":
    main()
