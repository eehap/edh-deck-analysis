#!/usr/bin/env python3
"""Find complete and near-complete combos for a Commander deck via Commander Spellbook,
then score each combo's robustness against the rest of the deck.

Sources (--source):
  api   POST https://backend.commanderspellbook.com/find-my-combos/  (included + 1 card away)
  bulk  https://json.commanderspellbook.com/variants.json.gz         (offline; also finds 2 away)
  auto  api, plus bulk for the 2-away search when --two-away is given (default)
Spellbook asks for: a named User-Agent, <= ~80 requests/minute, handling 429, and a credit link
back to commanderspellbook.com in anything you show users. Never page the whole dataset via the API.

Usage:
  python find_combos.py deck.json [--roles roles.json] [-o combos.json] [--two-away]
  python find_combos.py deck.json --response saved_spellbook.json   # offline / testing
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from edh_common import (CACHE_DIR, NetworkUnavailable, cache_get, cache_put, card_text,  # noqa: E402
                        card_type_line, dump_json, http, load_json, norm_name)

API = "https://backend.commanderspellbook.com/find-my-combos/"
BULK = "https://json.commanderspellbook.com/variants.json.gz"
CREDIT = "Combo data from Commander Spellbook (https://commanderspellbook.com)."
# Features that end the game (or leave opponents unable to play) - names verified against live Spellbook output
WIN_FEATURES = re.compile(
    r"win the game|loses? the game|"                                   # "Target opponent loses the game", alt wins
    r"exile all (?:of your )?opponents'? permanents|exile all permanents opponents control|"
    r"\block\b|opponents can't (?:cast|attack|untap)|creatures can't attack|"  # locks
    r"infinite turns|"
    r"infinite (?:damage|lifeloss|life loss)(?! to you)(?: for (?:target|each) opponent)?|"
    r"near-infinite (?:damage|lifeloss)(?: for (?:target|each) opponent)?|"
    r"infinite mill(?:ing)?(?! of yourself)(?!.*self)", re.I)
SELF_ONLY = re.compile(r"self-mill|to you\b|for all players", re.I)
MLD_FEATURE = re.compile(r"mass land denial|destroy all lands|opponents'? lands", re.I)
# Commander Spellbook bracketTag enum (verified from /schema/, Oct 2026)
BRACKET_TAGS = {"R": "Ruthless", "S": "Spicy", "P": "Powerful", "O": "Oddball", "C": "Core", "E": "Exhibition", "B": "Banned"}


# ---------------- fetching ----------------

def request_body(deck: dict) -> dict:
    cmd = [{"card": c["name"], "quantity": 1} for c in deck["cards"] if c["board"] == "commander"]
    main = [{"card": c["name"], "quantity": c["qty"]} for c in deck["cards"] if c["board"] == "main"]
    return {"commanders": cmd, "main": main}


def fetch_api(deck: dict) -> dict:
    body = request_body(deck)
    key = "|".join(sorted(f"{x['card']}" for x in body["commanders"] + body["main"]))
    cached = cache_get("spellbook_fmc", key, max_age_s=86400)
    if cached:
        return cached
    res = http(API, method="POST", body=body)
    # paginated responses: follow "next" if present
    results = res.get("results", res)
    nxt = res.get("next")
    while nxt:
        page = http(nxt, method="POST", body=body)
        for k, v in page.get("results", {}).items():
            if isinstance(v, list):
                results.setdefault(k, []).extend(v)
        nxt = page.get("next")
    res = {"results": results}
    cache_put("spellbook_fmc", key, res)
    return res


def load_bulk() -> list[dict]:
    import gzip
    import json
    import time
    p = CACHE_DIR / "spellbook_variants.json.gz"
    if not p.exists() or time.time() - p.stat().st_mtime > 86400:
        data = http(BULK, raw=True, timeout=600)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(gzip.compress(data) if data[:2] != b"\x1f\x8b" else data)
    with gzip.open(p, "rt", encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("variants", raw if isinstance(raw, list) else [])


def bulk_search(deck: dict, variants: list[dict], max_missing: int = 2) -> dict:
    names = {norm_name(c["name"]) for c in deck["cards"] if c["board"] in ("main", "commander")}
    names |= {norm_name(c["name"].split(" // ")[0]) for c in deck["cards"] if c["board"] in ("main", "commander")}
    ident = set(deck.get("color_identity", ""))
    out = {"included": [], "almostIncluded": [], "twoAway": []}
    for v in variants:
        if (v.get("legalities") or {}).get("commander") is False:
            continue
        vid = set((v.get("identity") or "").replace("C", ""))
        if not vid <= ident:
            continue
        pieces = [u["card"]["name"] for u in v.get("uses", []) if u.get("card")]
        missing = [p for p in pieces if norm_name(p) not in names and norm_name(p.split(" // ")[0]) not in names]
        if len(missing) == 0:
            out["included"].append(v)
        elif len(missing) == 1:
            out["almostIncluded"].append(v)
        elif len(missing) == 2 and max_missing >= 2:
            out["twoAway"].append(v)
    return {"results": out}


# ---------------- normalizing ----------------

def _names(v: dict) -> list[str]:
    return [u["card"]["name"] for u in v.get("uses", []) if u.get("card")]


def _templates(v: dict) -> list[str]:
    return [r["template"]["name"] for r in v.get("requires", []) if r.get("template")]


def normalize(v: dict, deck_names: set[str]) -> dict:
    pieces = _names(v)
    missing = [p for p in pieces if norm_name(p) not in deck_names and norm_name(p.split(" // ")[0]) not in deck_names]
    produces = [p["feature"]["name"] for p in v.get("produces", []) if p.get("feature")]
    vid = v.get("id")
    return {
        "id": vid, "url": f"https://commanderspellbook.com/combo/{vid}/" if vid else None,
        "pieces": pieces, "missing": missing, "templates_required": _templates(v),
        "produces": produces, "mana_needed": v.get("manaNeeded") or "",
        "identity": v.get("identity"), "bracket_tag": v.get("bracketTag"),
        "bracket_tag_name": BRACKET_TAGS.get(v.get("bracketTag")),
        "mass_land_denial": any(MLD_FEATURE.search(p) for p in produces),
        "popularity": v.get("popularity"), "salt": v.get("salt"),
        "prerequisites": " ".join(x for x in (v.get("easyPrerequisites"), v.get("notablePrerequisites")) if x),
        "steps": v.get("description", ""),
        "game_winning": bool(any(WIN_FEATURES.search(p) and not SELF_ONLY.search(p) for p in produces)),
    }


# ---------------- robustness ----------------

def mv_of(cost: str) -> int:
    total = 0
    for s in re.findall(r"\{([^}]+)\}", cost or ""):
        total += int(s) if s.isdigit() else (0 if s in ("X", "Y") else 1)
    return total


def tutor_kinds(deck: dict, roles: dict | None) -> list[tuple[str, str]]:
    """(card, kind) for every tutor in the deck; kind in any/creature/artifact/enchantment/instant/sorcery/..."""
    tutor_names = None
    if roles:
        tutor_names = {c["name"] for c in roles["cards"] if "tutor" in c.get("roles", {})}
    out = []
    for c in deck["cards"]:
        if c["board"] not in ("main", "commander"):
            continue
        if tutor_names is not None and c["name"] not in tutor_names:
            continue
        t = card_text(c["card"])
        m = re.search(r"search your library for (?:up to \w+ )?(?:an? |two |three )?([\w\s\-]*?)cards?", t, re.I)
        if not m:
            continue
        what = m.group(1).lower().strip()
        if re.search(r"land|plains|island|swamp|mountain|forest", what):
            continue
        kind = "any" if what in ("", "a") else what.split()[-1] if what else "any"
        if "legendary" in what and kind == "creature":
            kind = "legendary creature"
        out.append((c["name"], kind))
    return out


def robustness(combo: dict, deck: dict, by_name: dict, tutors: list, all_combos: list[dict],
               outlet_hints: dict[str, list[str]]) -> dict:
    cmd_names = {norm_name(c["name"]) for c in deck["cards"] if c["board"] == "commander"}
    pieces = combo["pieces"]
    n = len(pieces) + len(combo["templates_required"])
    s_pieces = 25 if n <= 2 else 15 if n == 3 else 5
    has_cmd = any(norm_name(p) in cmd_names for p in pieces)
    if has_cmd:
        s_pieces = min(25, s_pieces + 5)

    mv_total = sum(by_name[norm_name(p)]["card"].get("cmc", 0) for p in pieces if norm_name(p) in by_name
                   and norm_name(p) not in cmd_names)
    mv_total += mv_of(combo["mana_needed"])
    s_mana = 15 if mv_total <= 6 else max(0, round(15 - (mv_total - 6) * 1.5))

    coverage = []
    for p in pieces:
        if norm_name(p) in cmd_names:
            continue
        card = by_name.get(norm_name(p), {}).get("card", {})
        tl = card_type_line(card).lower()
        n_t = sum(1 for _, k in tutors if k == "any" or k in tl or (k == "permanent" and "instant" not in tl and "sorcery" not in tl))
        coverage.append(min(n_t, 2) / 2)
    s_tutor = round(20 * (sum(coverage) / len(coverage))) if coverage else 20

    others = [c for c in all_combos if c is not combo and not c["missing"]]
    shared = [c for c in others if set(c["produces"]) & set(combo["produces"]) or set(c["pieces"]) & set(pieces)]
    s_red = 0 if not shared else 5 if len(shared) == 1 else 10

    fragility, why = 15, []
    gy = re.search(r"graveyard", combo["prerequisites"] + " " + combo["steps"], re.I)
    if gy:
        fragility -= 4
        why.append("graveyard-dependent")
    for p in pieces:
        if norm_name(p) in cmd_names:
            continue
        tl = card_type_line(by_name.get(norm_name(p), {}).get("card", {}))
        if "Creature" in tl:
            fragility -= 2
            why.append(f"{p} dies to creature removal/wipes")
        elif "Artifact" in tl or "Enchantment" in tl:
            fragility -= 1
            why.append(f"{p} dies to artifact/enchantment removal")
    s_frag = max(0, fragility)

    if combo["game_winning"]:
        s_out, outlet = 15, "ends the game (win / lock / exile-all)"
    else:
        outlet = None
        for feat in combo["produces"]:
            f = feat.lower()
            for key, cards in outlet_hints.items():
                if key in f and cards:
                    outlet = f"{feat} → outlet in deck: {', '.join(cards[:3])}"
                    break
            if outlet:
                break
        s_out = 15 if outlet else 7
        outlet = outlet or "needs an outlet; none detected by rules — check manually"

    total = s_pieces + s_mana + s_tutor + s_red + s_frag + s_out
    return {"score": total, "parts": {"pieces": s_pieces, "mana": s_mana, "tutor_access": s_tutor,
                                       "redundancy": s_red, "fragility": s_frag, "outcome": s_out},
            "total_mv": mv_total, "fragility_notes": why, "outcome_note": outlet,
            "early_two_card": (len(pieces) <= 2 and not combo["templates_required"]
                               and mv_total - mv_of(combo["mana_needed"]) <= 8
                               and max((by_name.get(norm_name(p), {}).get("card", {}).get("cmc", 0)
                                        for p in pieces if norm_name(p) not in cmd_names), default=0) <= 4)}


def outlet_hints_for(deck: dict) -> dict[str, list[str]]:
    hints = {"death trigger": [], "lifeloss": [], "mana": [], "token": [], "damage": [], "etb": [], "sacrifice": []}
    for c in deck["cards"]:
        if c["board"] not in ("main", "commander"):
            continue
        t = card_text(c["card"]).lower()
        if re.search(r"(dies|is put into a graveyard)[^.]*(loses \d+ life|deals \d+ damage)", t) or \
                re.search(r"whenever [^.]*dies, [^.]*(each opponent|target player) loses", t):
            hints["death trigger"].append(c["name"])
            hints["sacrifice"].append(c["name"])
        if re.search(r"\{x\}", c["card"].get("mana_cost", "").lower()) or re.search(r"\{\d\}: [^.]*(\+1/\+1 counter|damage)", t):
            hints["mana"].append(c["name"])
        if re.search(r"sacrifice (?:a|another) creature:", t):
            hints["token"].append(c["name"])
        if re.search(r"whenever [^.]*enters[^.]*(each opponent loses|deals \d+ damage)", t):
            hints["etb"].append(c["name"])
    return hints


def analyze(deck: dict, raw: dict, roles: dict | None = None) -> dict:
    res = raw.get("results", raw)
    deck_names = set()
    by_name = {}
    for c in deck["cards"]:
        if c["board"] in ("main", "commander"):
            for k in (c["name"], c["name"].split(" // ")[0]):
                deck_names.add(norm_name(k))
                by_name[norm_name(k)] = c
    included = [normalize(v, deck_names) for v in res.get("included", [])]
    almost = [normalize(v, deck_names) for v in res.get("almostIncluded", [])]
    two = [normalize(v, deck_names) for v in res.get("twoAway", [])]
    tutors = tutor_kinds(deck, roles)
    hints = outlet_hints_for(deck)
    for c in included:
        c["robustness"] = robustness(c, deck, by_name, tutors, included, hints)
    for c in almost:
        c["robustness"] = robustness(c, deck, by_name, tutors, included, hints)
    included.sort(key=lambda c: -c["robustness"]["score"])
    almost.sort(key=lambda c: (-(c["popularity"] or 0)))

    # near-combos grouped by the single missing card: one add can unlock several
    unlocks: dict[str, list[str]] = {}
    for c in almost:
        for m in c["missing"]:
            unlocks.setdefault(m, []).append(" + ".join(c["pieces"]))
    other_buckets = {k: len(v) for k, v in res.items() if isinstance(v, list)
                     and k not in ("included", "almostIncluded", "twoAway")}
    other_buckets.update(raw.get("other_bucket_counts", {}))
    est = raw.get("estimate_bracket")
    if est and est.get("bracketTag"):
        est = {**est, "bracketTag_name": BRACKET_TAGS.get(est["bracketTag"])}
    return {
        "schema": "edh-combos/1",
        "credit": CREDIT,
        "commanders": deck.get("commanders", []),
        "identity": res.get("identity") or deck.get("color_identity"),
        "tutors_in_deck": [f"{n} ({k})" for n, k in tutors],
        "included": included,
        "almost_included": almost,
        "two_away": two[:50],
        "single_card_unlocks": dict(sorted(unlocks.items(), key=lambda kv: -len(kv[1]))),
        "early_two_card_combos": [" + ".join(c["pieces"]) for c in included if c["robustness"]["early_two_card"]],
        "game_winning_combos": [" + ".join(c["pieces"]) for c in included if c["game_winning"]],
        "mass_land_denial_combos": [" + ".join(c["pieces"]) for c in included if c["mass_land_denial"]],
        "bracket_tags": {" + ".join(c["pieces"]): c["bracket_tag_name"] or c["bracket_tag"] for c in included},
        "spellbook_estimate": est,
        "bracket_tag_legend": BRACKET_TAGS,
        "other_buckets_counts": other_buckets,
    }


def to_markdown(r: dict) -> str:
    L = [f"## Combos — {' & '.join(r['commanders'])}", ""]
    if not r["included"]:
        L.append("No complete combos found.")
    else:
        L += ["| Combo | Result | Game-winning | Spellbook tag | Robustness | Notes |", "|---|---|---|---|---|---|"]
        for c in r["included"]:
            rb = c["robustness"]
            notes = "; ".join(filter(None, [rb["outcome_note"],
                                            "produces Mass Land Denial" if c["mass_land_denial"] else "",
                                            ", ".join(rb["fragility_notes"][:2]),
                                            "early 2-card" if rb["early_two_card"] else ""]))
            L.append(f"| [{' + '.join(c['pieces'])}]({c['url']}) | {', '.join(c['produces'][:2])} | "
                     f"{'yes' if c['game_winning'] else 'needs outlet'} | {c['bracket_tag_name'] or c['bracket_tag'] or '-'} | "
                     f"{rb['score']}/100 | {notes} |")
    est = r.get("spellbook_estimate")
    if est and est.get("bracketTag"):
        L += ["", f"Commander Spellbook's deck-level bracket tag: **{est.get('bracketTag_name') or est['bracketTag']}** "
                  "(Spellbook's own classification - judgment input, not an official bracket)."]
    if r.get("mass_land_denial_combos"):
        L.append("Combos that produce Mass Land Denial: " + "; ".join(r["mass_land_denial_combos"])
                 + ". Brackets 1-3 rule out mass land denial; weigh this in the bracket estimate.")
    if r["almost_included"]:
        L += ["", f"### One card away ({len(r['almost_included'])})"]
        for card, combos in list(r["single_card_unlocks"].items())[:10]:
            L.append(f"- **{card}** completes {len(combos)}: " + "; ".join(combos[:3]))
    if r["two_away"]:
        L += ["", f"### Two cards away (top {min(10, len(r['two_away']))} by popularity)"]
        for c in sorted(r["two_away"], key=lambda c: -(c["popularity"] or 0))[:10]:
            L.append(f"- {' + '.join(c['pieces'])} (missing {', '.join(c['missing'])}) → {', '.join(c['produces'][:2])}")
    L += ["", f"_{r['credit']}_"]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("--roles")
    ap.add_argument("-o", "--out", default="combos.json")
    ap.add_argument("--md")
    ap.add_argument("--source", choices=["api", "bulk", "auto"], default="auto")
    ap.add_argument("--two-away", action="store_true")
    ap.add_argument("--response", help="use a saved find-my-combos response instead of calling the API")
    a = ap.parse_args()
    deck = load_json(a.deck)
    roles = load_json(a.roles) if a.roles else None
    if a.response:
        raw = load_json(a.response)
    else:
        raw = None
        if a.source in ("api", "auto"):
            try:
                raw = fetch_api(deck)
            except NetworkUnavailable as e:
                print(f"[combos] API unreachable: {e}", file=sys.stderr)
                if a.source == "api":
                    sys.exit(2)
        if raw is None or (a.two_away and a.source != "api"):
            try:
                b = bulk_search(deck, load_bulk(), 2 if a.two_away else 1)
                if raw is None:
                    raw = b
                else:
                    raw.setdefault("results", {})["twoAway"] = b["results"]["twoAway"]
            except NetworkUnavailable as e:
                if raw is None:
                    print(f"[combos] bulk file unreachable too: {e}\nNo combo data source available. "
                          "Fall back to known-combo reasoning and say so in the report.", file=sys.stderr)
                    sys.exit(2)
    r = analyze(deck, raw, roles)
    dump_json(r, a.out)
    md = to_markdown(r)
    if a.md:
        open(a.md, "w").write(md)
    print(md, file=sys.stderr)


if __name__ == "__main__":
    main()
