#!/usr/bin/env python3
"""Score cut candidates in the deck, score add candidates, and pair them into swaps.

Deterministic first pass; the model then vetoes swaps that break the deck's theme,
rewrites the reasons in plain language, and may add swaps of its own.

Cut score (higher = cut first). All of a card's roles are weighed together:
  +3  per surplus role, ONLY if every role the card fills is above target (a removal spell that is also
      card draw the deck needs is not cut for the removal surplus)        +1  above target but in range
  -4w fills a role below its range (w = weight)    -2w below target
  -2w engine role; -2 cheated (put into play without casting): neither is cut for surplus or for MV
  +4  no role at all (off-plan) / model note says off-plan
  +3  MV >= 6 without a full-weight wincon/engine role (high cost, low impact) - never for cheated cards
  +1.5 MV well above the median of the cards sharing its main role (inefficient) - never for cheated cards
  +1  EDHREC synergy < 0, +1 inclusion < 10% (only when EDHREC stats are available)
  -8  piece of a complete combo
  must_cut list: Game Changers over the bracket cap, mass land denial / extra turns in Bracket <= 3
Add score:
  +4w per role below its range, +2w below target, -1 per role above range
  +synergy*5 (EDHREC), +1 (rank < 1000) / +0.5 (rank < 5000), -0.3 per MV above 3
  +2 per near-combo it completes (only Bracket >= 3, and not an early two-card combo in Bracket 3)
  +2 already in the user's collection (candidates.py --collection, mode "prefer"). Ownership breaks ties and
     tips close calls, but never qualifies an add on its own: an add still has to close a role gap, bring
     synergy or complete a combo. In mode "only" candidates.py has already removed cards the user doesn't own.
Swap score = cut + add - 0.5 * max(0, add MV - cut MV). Greedy pairing, role totals updated after each swap.

Usage:
  python score_swaps.py deck.json structure.json candidates.json [--combos combos.json]
         [--bracket 3] [--max-swaps 10] [--protect "Card A" --protect "Card B"] [-o swaps.json] [--md swaps.md]
"""
from __future__ import annotations

import argparse
import copy
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(__file__))
from edh_common import dump_json, load_json, norm_name  # noqa: E402

GC_CAP = {1: 0, 2: 0, 3: 3}


def role_state(role_table):
    return {r["role"]: dict(r) for r in role_table}


def status(r):
    if r.get("min") is None:
        return "info"
    return "low" if r["have"] < r["min"] else "high" if r["have"] > r["max"] else "ok"


def tgt(r):
    return r["target"] if isinstance(r.get("target"), (int, float)) else r["have"]


def cut_score(card, rs, combo_pieces, deck_stats, role_median, rank=None):
    """Weigh ALL of a card's roles. A role surplus only counts when every role the card fills is in surplus;
    engine cards and cheated cards (put into play without casting) are never cut for surplus or castability."""
    s, why = 0.0, []
    roles = card.get("roles", {})
    cheated = bool(card.get("cheated"))
    engine_w = roles.get("engine", {}).get("weight", 0)
    scored = {k: v for k, v in roles.items() if k != "land" and rs.get(k) and status(rs[k]) != "info"}
    over = {k for k in scored if status(rs[k]) == "high"}
    above = {k for k in scored if rs[k]["have"] > tgt(rs[k])}
    needed = {k for k in scored if rs[k]["have"] <= tgt(rs[k])}

    if cheated:
        s -= 2; why.append("cheated into play (polymorph/reveal target): not judged on casting cost")
    if engine_w >= 0.5:
        s -= 2 * engine_w; why.append("engine for the deck's plan")
    if scored and not needed and not cheated and engine_w < 0.5:
        for k in sorted(over):
            s += 3 * scored[k]["weight"] + 0.25 * card.get("cmc", 0)
            why.append(f"{k} is over its range ({rs[k]['have']:g} > {rs[k]['max']})")
        for k in sorted(above - over):
            s += 1 * scored[k]["weight"]; why.append(f"{k} above target")
    elif over and needed:
        why.append(f"also fills {', '.join(sorted(needed))}, so the {', '.join(sorted(over))} surplus isn't a reason to cut it")
    for k in needed:
        r, w = rs[k], scored[k]["weight"]
        if status(r) == "low":
            s -= 4 * w; why.append(f"keeps {k} from dropping further (already low)")
        elif r["have"] < tgt(r):
            s -= 2 * w
    if (not roles or "off-plan" in (card.get("model_note") or "").lower()) and not cheated:
        s += 4; why.append("no functional role / off-plan")
    full = {k for k, v in roles.items() if v["weight"] >= 1.0}
    if rank is not None and rank < 150:
        s -= 1.5; why.append("format staple (top-150 EDHREC rank)")
    if not cheated and card.get("cmc", 0) >= 6 and not (full & {"wincon", "engine", "mass_interaction"}):
        s += 3; why.append(f"MV {card['cmc']:g} without a game-winning or engine role")
    main_role = max(((k, v["weight"]) for k, v in roles.items() if k != "land"), key=lambda kv: kv[1], default=(None, 0))[0]
    if not cheated and main_role and main_role in role_median and card.get("cmc", 0) >= role_median[main_role] + 1.5:
        s += 1.5; why.append(f"pricier than the typical {main_role} card here (MV {card['cmc']:g} vs median {role_median[main_role]:g})")
    st_ = deck_stats.get(card["name"])
    if st_:
        if (st_.get("synergy") or 0) < 0:
            s += 1; why.append(f"EDHREC synergy {st_['synergy']:+.0%}")
        if st_.get("inclusion_rate") is not None and st_["inclusion_rate"] < 0.10:
            s += 1; why.append(f"in only {st_['inclusion_rate']:.0%} of decks for this commander")
    if norm_name(card["name"]) in combo_pieces:
        s -= 8; why.append("piece of a complete combo")
    return round(s, 2), why


OWNED_BONUS = 2.0
OWNED_NOTE = "already in your collection"


def add_score(c, rs, bracket, early_names, prefer_owned=False):
    s, why = 0.0, []
    roles = dict(c.get("roles_rule", {}))
    for h in c.get("role_hints", []):
        roles[h] = max(roles.get(h, 0), 1.0)
    for role, w in roles.items():
        r = rs.get(role)
        if not r or role == "land" or r.get("min") is None:
            continue
        st = status(r)
        if st == "low":
            s += 4 * w; why.append(f"adds {role} (below range)")
        elif r["have"] < tgt(r):
            s += 2 * w; why.append(f"adds {role} (below target)")
        elif st == "high":
            s -= 1
    if c.get("synergy") is not None:
        s += 5 * c["synergy"]
        if c["synergy"] >= 0.15:
            why.append(f"EDHREC synergy {c['synergy']:+.0%}")
    rank = c.get("edhrec_rank")
    if rank:
        s += 1 if rank < 1000 else 0.5 if rank < 5000 else 0
    s -= 0.3 * max(0, (c.get("cmc") or 0) - 3)
    if c.get("completes") and (bracket is None or bracket >= 3):
        if bracket == 3 and set(c["completes"]) & early_names:
            pass
        else:
            s += 2 * len(c["completes"]); why.append(f"completes {len(c['completes'])} combo(s)")
    if c.get("owned"):
        if prefer_owned:
            s += OWNED_BONUS
        why.append(OWNED_NOTE)
    return round(s, 2), why, roles


def qualifies(why: list[str]) -> bool:
    """An add needs a real reason (gap, synergy, combo); owning it isn't one."""
    return any(w != OWNED_NOTE for w in why)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck"); ap.add_argument("structure"); ap.add_argument("candidates")
    ap.add_argument("--combos"); ap.add_argument("--bracket", type=int)
    ap.add_argument("--max-swaps", type=int, default=10)
    ap.add_argument("--protect", action="append", default=[])
    ap.add_argument("-o", "--out", default="swaps.json"); ap.add_argument("--md")
    a = ap.parse_args()
    deck, st, cd = load_json(a.deck), load_json(a.structure), load_json(a.candidates)
    combos = load_json(a.combos) if a.combos else {"included": []}
    combo_pieces = {norm_name(p) for c in combos.get("included", []) for p in c["pieces"]}
    early = set(combos.get("early_two_card_combos", []))
    rs = role_state(st["role_table"])
    protect = {norm_name(p) for p in a.protect}
    deck_stats = cd.get("deck_card_stats", {})
    card_data = {c["name"]: c["card"] for c in deck["cards"]}

    by_role: dict[str, list[float]] = {}
    main_cards = [c for c in st["cards"] if c["board"] == "main"]
    for c in main_cards:
        for role in c.get("roles", {}):
            by_role.setdefault(role, []).append(c.get("cmc", 0))
    role_median = {r: statistics.median(v) for r, v in by_role.items() if len(v) >= 3}

    # must-cuts
    must = []
    gc = [c for c in main_cards if "game_changer" in c.get("flags", [])]
    cap = GC_CAP.get(a.bracket) if a.bracket else None
    if cap is not None and len(gc) > cap:
        must += [{"name": c["name"], "reason": f"Game Changer #{i + 1} of {len(gc)}; Bracket {a.bracket} allows {cap}"}
                 for i, c in enumerate(gc) if i >= cap]
    if a.bracket and a.bracket <= 3:
        for c in main_cards:
            if "mld" in c.get("flags", []):
                must.append({"name": c["name"], "reason": f"mass land denial is not allowed in Bracket {a.bracket}"})
            if "extra_turn" in c.get("flags", []):
                must.append({"name": c["name"], "reason": f"extra turns: check it can't chain (not allowed in Bracket {a.bracket})"})

    conflicts = []
    for c in combos.get("included", []):
        two = len(c["pieces"]) <= 2 and not c.get("templates_required")
        if two and a.bracket and a.bracket <= 2:
            conflicts.append(f"Two-card combo {' + '.join(c['pieces'])}: Bracket {a.bracket} expects no intentional "
                             "two-card combos. Cut one piece or play the deck at Bracket 3+.")
        elif two and a.bracket == 3 and c.get("robustness", {}).get("early_two_card"):
            conflicts.append(f"Two-card combo {' + '.join(c['pieces'])} looks assemblable before turn 6, which "
                             "Bracket 3 rules out. Cut a piece or call the deck Bracket 4.")

    nonland_cuts = []
    for c in main_cards:
        if "land" in c.get("roles", {}) and c["roles"]["land"]["weight"] >= 1.0:
            continue
        if norm_name(c["name"]) in protect:
            continue
        s, why = cut_score(c, rs, combo_pieces, deck_stats, role_median, card_data.get(c["name"], {}).get("edhrec_rank"))
        nonland_cuts.append({"name": c["name"], "cmc": c.get("cmc", 0), "score": s, "why": why,
                             "roles": {k: v["weight"] for k, v in c.get("roles", {}).items()}})
    nonland_cuts.sort(key=lambda x: -x["score"])

    adds = []
    gc_after_must = len(gc) - sum(1 for m in must if "Game Changer" in m["reason"])
    coll = cd.get("collection")
    prefer_owned = bool(coll) and coll.get("mode") == "prefer"
    for c in cd.get("candidates", []):
        if a.bracket and a.bracket <= 2 and c.get("completes"):
            continue  # Bracket 2: no intentional combos
        if cap is not None and c.get("game_changer") and gc_after_must >= cap:
            continue
        s, why, roles = add_score(c, rs, a.bracket, early, prefer_owned)
        adds.append({**{k: c.get(k) for k in ("name", "cmc", "price_usd", "sources", "synergy", "inclusion_rate",
                                              "game_changer", "type_line", "owned")}, "score": s, "why": why,
                     "roles": roles})
    adds.sort(key=lambda x: -x["score"])

    # greedy pairing with live role totals
    live = copy.deepcopy(rs)
    used_cut, used_add, swaps = set(), set(), []
    gc_added = 0      # Game Changers added so far: the cap applies to the deck after ALL swaps
    must_names = {m["name"] for m in must}
    for _ in range(a.max_swaps):
        best = None
        must_left = [c for c in nonland_cuts if c["name"] in must_names and c["name"] not in used_cut]
        cut_pool = must_left or [c for c in nonland_cuts if c["name"] not in used_cut][:25]
        for cut in cut_pool:
            cs, cwhy = cut_score({**next(x for x in main_cards if x["name"] == cut["name"])}, live,
                                 combo_pieces, deck_stats, role_median, card_data.get(cut["name"], {}).get("edhrec_rank"))
            if cut["name"] in must_names:
                cs += 100
                cwhy = [m["reason"] for m in must if m["name"] == cut["name"]] + cwhy
            for add in adds[:60]:
                if add["name"] in used_add:
                    continue
                if cap is not None and add.get("game_changer") and gc_after_must + gc_added >= cap:
                    continue
                as_, awhy, _ = add_score(next(x for x in cd["candidates"] if x["name"] == add["name"]), live, a.bracket,
                                         early, prefer_owned)
                if as_ < 1.0 or not qualifies(awhy):
                    continue  # an add that doesn't close a gap (or add synergy/combo) is not a swap
                score = cs + as_ - 0.5 * max(0, (add["cmc"] or 0) - (cut["cmc"] or 0))
                if best is None or score > best[0]:
                    best = (score, cut, add, cwhy, awhy, cs, as_)
        if (not best or best[0] <= 0) and must_left:
            cut = must_left[0]
            main_role = max(((k, w) for k, w in cut["roles"].items() if k != "land"), key=lambda kv: kv[1], default=("plan", 0))[0]
            used_cut.add(cut["name"])
            for role, w in cut["roles"].items():
                if role in live:
                    live[role]["have"] = round(live[role]["have"] - w, 2)
            swaps.append({"cut": cut["name"], "add": None, "score": 100.0,
                          "cut_reasons": [m["reason"] for m in must if m["name"] == cut["name"]],
                          "add_reasons": [f"replace with a non-Game-Changer {main_role} card (no candidate fit)"],
                          "cut_mv": cut["cmc"], "add_mv": None, "add_price_usd": None, "add_sources": [],
                          "add_owned": None, "must_cut": True})
            continue
        if not best or best[0] <= 0:
            break
        score, cut, add, cwhy, awhy, cs, as_ = best
        used_cut.add(cut["name"]); used_add.add(add["name"])
        gc_added += 1 if add.get("game_changer") else 0
        for role, w in cut["roles"].items():
            if role in live:
                live[role]["have"] = round(live[role]["have"] - w, 2)
        for role, w in add["roles"].items():
            if role in live:
                live[role]["have"] = round(live[role]["have"] + w, 2)
        swaps.append({"cut": cut["name"], "add": add["name"], "score": round(score, 2),
                      "cut_reasons": cwhy, "add_reasons": awhy,
                      "cut_mv": cut["cmc"], "add_mv": add["cmc"], "add_price_usd": add["price_usd"],
                      "add_sources": add["sources"], "add_owned": add.get("owned"),
                      "must_cut": cut["name"] in must_names})

    open_cuts = [c for c in nonland_cuts if c["name"] not in used_cut and c["score"] >= 3][:5]
    mana = st.get("mana", {})
    land_note = None
    if mana:
        diff = mana["karsten_recommended_lands"] - mana["land_count"]
        if diff >= 1.5:
            land_note = (f"Mana analysis wants ~{round(diff)} more land(s): make that many extra swaps of the "
                         f"highest-scoring cuts for lands (a dual in {deck.get('color_identity')} or a basic).")
        elif diff <= -2:
            land_note = f"Deck could run ~{round(-diff)} fewer lands; consider cutting basics for the top adds."

    coll_note = None
    if coll:
        real = [s for s in swaps if s["add"]]
        own_n = sum(1 for s in real if s["add_owned"])
        buy = [s for s in real if not s["add_owned"]]
        cost = sum(s["add_price_usd"] or 0 for s in buy)
        unpriced = sum(1 for s in buy if s["add_price_usd"] is None)
        coll_note = {"adds_owned": own_n, "adds_to_buy": len(buy), "cost_to_buy_usd": round(cost, 2),
                     "unpriced_to_buy": unpriced, "mode": coll.get("mode"),
                     "deck_cards_not_owned": coll.get("deck_cards_not_owned", [])}

    res = {"schema": "edh-swaps/1", "bracket": a.bracket, "must_cut": must, "bracket_conflicts": conflicts, "swaps": swaps,
           "cuts_without_a_good_add": open_cuts,
           "top_cuts": nonland_cuts[:15], "top_adds": adds[:15],
           "role_table_after": [{"role": r, "have": v["have"], "status": status(v)} for r, v in live.items()],
           "land_note": land_note, "protected": sorted(a.protect), "collection": coll_note}
    dump_json(res, a.out)
    L = ["## Suggested swaps", "", "| # | Cut | Add | Why |", "|---|---|---|---|"]
    for i, s in enumerate(swaps, 1):
        add_why = [w for w in s["add_reasons"] if w != OWNED_NOTE]
        why = "; ".join((s["cut_reasons"][:2] or ["-"])) + " → " + "; ".join(add_why[:2] or ["-"])
        if s.get("add_owned"):
            price = " (owned)"
        else:
            price = f" (${s['add_price_usd']:.2f})" if s["add_price_usd"] is not None else ""
        L.append(f"| {i} | {s['cut']} | {s['add'] or '(your pick)'}{price} | {why} |")
    if coll_note:
        line = (f"**Collection:** {coll_note['adds_owned']} of {coll_note['adds_owned'] + coll_note['adds_to_buy']} "
                f"adds are already in your collection")
        if coll_note["adds_to_buy"]:
            line += (f"; buying the other {coll_note['adds_to_buy']} costs about ${coll_note['cost_to_buy_usd']:.2f}"
                     + (f" ({coll_note['unpriced_to_buy']} without a price)" if coll_note["unpriced_to_buy"] else ""))
        line += "."
        n = coll_note["deck_cards_not_owned"]
        if n and len(n) <= 25:
            line += f" {len(n)} card(s) in the deck aren't in the collection: " + ", ".join(n) + "."
        elif n:
            line += (f" {len(n)} cards in the deck aren't in the collection (list in swaps.json); if that's unexpected, "
                     "the export may cover only part of the collection or leave out cards already sleeved in decks.")
        L += ["", line]
    if must:
        L += ["", "**Must cut for the bracket:** " + "; ".join(f"{m['name']} ({m['reason']})" for m in must)]
    if conflicts:
        L += [""] + [f"**Bracket conflict:** {c}" for c in conflicts]
    if open_cuts:
        L += ["", "**Also worth cutting (no strong add found among candidates):** " +
              "; ".join(f"{c['name']} ({c['why'][0] if c['why'] else ''})" for c in open_cuts)]
    if land_note:
        L += ["", land_note]
    md = "\n".join(L) + "\n"
    if a.md:
        open(a.md, "w").write(md)
    print(md, file=sys.stderr)


if __name__ == "__main__":
    main()
