#!/usr/bin/env python3
"""Generate add candidates for a Commander deck and collect EDHREC stats for cards already in it.

Candidate sources (each optional; whatever is available is used):
  --edhrec-json      saved EDHREC data: the output of scripts/browser/edhrec_candidates.js (candidates with card
                     data + deck card stats) or a raw commander page from json.edhrec.com.
  --candidates-json  cards you or a browser snippet supply (scripts/browser/scryfall_search.js output, a card
                     table, or a list of Scryfall-shaped / slim cards). Each may carry "role_hint".
  edhrec (live)      https://json.edhrec.com/pages/commanders/{slug}.json  UNOFFICIAL, cached 24 h, attribute it.
  scryfall (live)    /cards/search per under-target role (2 req/s), filtered by identity, legality, budget, bracket.
  spellbook          cards completing a one-card-away combo (from combos.json), only if the bracket allows.
  --extra            a JSON list of card names to consider (resolved via the local index or Scryfall).
  --collection       OPTIONAL: what the user owns (CSV export from Moxfield/ManaBox/Deckbox/Dragon Shield/TCGplayer/
                     Archidekt, plain "qty name" text, or collection.json - see collection.py). Owned cards that fit
                     the deck become candidates themselves (source "collection"), every candidate is marked
                     owned / not owned, and owned cards skip the budget filter (they cost nothing to add).
                     --collection-mode prefer (default): owned cards get a bonus in score_swaps.py.
                     --collection-mode only: only owned cards are kept as adds.
                     Card data for the owned cards comes from --collection-cards (browser snippet
                     scripts/browser/collection_cards.js), the local Scryfall index, or Scryfall's API.
When nothing yields candidates, the script prints each role gap with a ready Scryfall query (and a
window.QUERIES line for scripts/browser/scryfall_search.js), and stores them in candidates.json["queries"].

Usage:
  python candidates.py deck.json structure.json [--combos combos.json] [--bracket 3] [--budget 10]
         [--strategy polymorph] [--edhrec-json edhrec.json] [--candidates-json cards.json]
         [--extra names.json] [--per-role 25] [--offline] [-o candidates.json]
         [--collection my_collection.csv [--collection-mode prefer|only] [--collection-cards owned_cards.json]]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from edh_common import (NetworkUnavailable, cache_get, cache_put, dump_json, expand_cards,  # noqa: E402
                        http, load_json, norm_name)
import tag_roles  # noqa: E402  (copy of edh-deck-structure/scripts/tag_roles.py)

# Scryfall otag slugs verified against the Oracle Tags bulk file (Oct 2026)
ROLE_QUERIES = {
    "ramp": "(otag:mana-rock OR otag:mana-dork OR otag:land-ramp)",
    "card_advantage": "(otag:draw-engine OR otag:burst-draw OR otag:card-advantage)",
    "targeted_interaction": "(otag:spot-removal OR otag:counterspell)",
    "mass_interaction": "(otag:sweeper OR otag:sweeper-one-sided OR otag:board-wipe)",
    "protection": "(otag:gives-hexproof OR otag:gives-indestructible OR otag:gives-protection OR otag:tax-attack)",
    "tutor": "otag:tutor -otag:tutor-land",
    "recursion": "(otag:reanimate-creature OR otag:mass-reanimation OR otag:recursion)",
    "wincon": "(otag:alternate-win-condition OR otag:win-condition)",
    "engine": "(otag:polymorph OR otag:consult-onto-battlefield)",
    "tokens": "otag:repeatable-creature-tokens",
}
# strategy-specific extra searches (role hint, query)
STRATEGY_QUERIES = {
    "polymorph": [("hits", "t:creature cmc>=6")],
    "cheat": [("hits", "t:creature cmc>=6")],
    "reanimator": [("hits", "t:creature cmc>=6")],
}
GC_CAP = {1: 0, 2: 0, 3: 3}


def edhrec_slug(names: list[str]) -> str:
    def one(n):
        n = n.split(" // ")[0].lower()
        n = re.sub(r"[^a-z0-9\s-]", "", n)
        return re.sub(r"\s+", "-", n.strip())
    return "-".join(sorted(one(n) for n in names))


def walk_edhrec(data) -> dict[str, dict]:
    """name -> {synergy, inclusion_rate, list} from a raw EDHREC commander page (layout undocumented)."""
    out: dict[str, dict] = {}

    def walk(o, header=None):
        if isinstance(o, dict):
            h = o.get("header") or header
            if "name" in o and ("synergy" in o or "num_decks" in o or "inclusion" in o):
                inc, pot = o.get("inclusion") or o.get("num_decks"), o.get("potential_decks")
                out.setdefault(o["name"], {"synergy": o.get("synergy"),
                                           "inclusion_rate": round(inc / pot, 3) if inc and pot else None, "list": h})
            for v in o.values():
                walk(v, h)
        elif isinstance(o, list):
            for v in o:
                walk(v, header)
    walk(data)
    return out


def scryfall_search(q: str, limit: int) -> list[dict]:
    res = http("https://api.scryfall.com/cards/search?order=edhrec&q=" + urllib.parse.quote(q))
    if res.get("__http_status") == 404:
        return []
    return res.get("data", [])[:limit]


def resolve_names(names: list[str], offline: bool) -> dict[str, dict]:
    out = {}
    try:
        import scryfall_data as sd  # optional: present if copied from intake
        idx = sd.load_index()
    except Exception:
        idx = None
    missing = []
    for n in names:
        oid = idx["names"].get(norm_name(n)) if idx else None
        if oid:
            out[n] = idx["cards"][oid]
        else:
            missing.append(n)
    if offline:
        return out
    for i in range(0, len(missing), 75):
        try:
            res = http("https://api.scryfall.com/cards/collection", method="POST",
                       body={"identifiers": [{"name": n} for n in missing[i:i + 75]]})
        except NetworkUnavailable:
            break
        for c in res.get("data", []):
            out[c["name"]] = c
    return out


def resolve_collection(names: list[str], offline: bool) -> tuple[list[dict], list[str]]:
    """Card data for owned names: local index first, then Scryfall /cards/collection (cached 7 days)."""
    try:
        import scryfall_data as sd
        idx = sd.load_index()
    except Exception:
        idx = None
    found, missing = [], []
    for n in names:
        oid = None
        if idx:
            oid = idx["names"].get(norm_name(n)) or idx["names"].get(norm_name(n.split(" // ")[0]))
        if oid:
            found.append(idx["cards"][oid])
        else:
            missing.append(n)
    if offline or not missing:
        return found, missing
    still = []
    for i in range(0, len(missing), 75):
        chunk = missing[i:i + 75]
        key = "|".join(sorted(chunk))
        res = cache_get("scryfall_collection", key, 7 * 86400)
        if res is None:
            try:
                res = http("https://api.scryfall.com/cards/collection", method="POST",
                           body={"identifiers": [{"name": n.split(" // ")[0]} for n in chunk]})
            except NetworkUnavailable:
                return found, missing[i:] + still
            cache_put("scryfall_collection", key, res)
        found += res.get("data", [])
        still += [x.get("name", "?") for x in res.get("not_found", [])]
    return found, still


def card_roles(card: dict) -> tuple[dict, set]:
    """Role weights from oracle text plus oracle tags when the card carries them (tags vetoed as in tag_roles)."""
    roles, flags, _ = tag_roles.text_signals(card, {})
    if card.get("otags"):
        o, of = tag_roles.otag_signals(card["otags"])
        flags |= of
        tag_roles._veto(roles, flags, o, card)
        for k, v in o.items():
            roles[k] = max(roles.get(k, 0), v)
    return roles, flags


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck"); ap.add_argument("structure")
    ap.add_argument("--combos"); ap.add_argument("--bracket", type=int)
    ap.add_argument("--budget", type=float, help="max USD per added card")
    ap.add_argument("--strategy", help="defaults to the profile recorded in structure.json")
    ap.add_argument("--per-role", type=int, default=25)
    ap.add_argument("--edhrec-json"); ap.add_argument("--candidates-json")
    ap.add_argument("--extra", help="JSON list of extra candidate names")
    ap.add_argument("--offline", action="store_true", help="don't try live EDHREC/Scryfall")
    ap.add_argument("--collection", help="what the user owns (CSV export, text list, or collection.json)")
    ap.add_argument("--collection-mode", choices=["prefer", "only"], default="prefer")
    ap.add_argument("--collection-cards", help="card data for owned cards (scripts/browser/collection_cards.js)")
    ap.add_argument("-o", "--out", default="candidates.json")
    a = ap.parse_args()
    deck, st = load_json(a.deck), load_json(a.structure)
    strategy = a.strategy or st.get("strategy_profile", "midrange")
    ident = deck.get("color_identity") or "C"
    in_deck = {norm_name(c["name"]) for c in deck["cards"] if c["board"] in ("main", "commander")}
    in_deck |= {norm_name(c["name"].split(" // ")[0]) for c in deck["cards"] if c["board"] in ("main", "commander")}
    gc_in_deck = sum(1 for c in deck["cards"] if c["board"] in ("main", "commander") and c["card"].get("game_changer"))
    gc_cap = GC_CAP.get(a.bracket, 99) if a.bracket else 99
    allow_gc = gc_in_deck < gc_cap
    notes, cands, filtered = [], {}, {"in_deck": 0, "identity": 0, "legality": 0, "game_changer": 0, "budget": 0}
    owned = None
    if a.collection:
        import collection as coll_mod
        coll = coll_mod.parse(a.collection)
        owned = coll_mod.Owned(coll)
        notes.append(f"Collection ({coll['format']}): {len(coll['cards'])} distinct cards, "
                     f"{sum(coll['cards'].values())} copies; mode '{a.collection_mode}'.")
        if coll["unparsed"]:
            notes.append(f"{len(coll['unparsed'])} collection line(s) not understood, e.g. {coll['unparsed'][0]}")

    def add(card: dict, source: str, role_hint: str | None = None, **extra):
        name = card["name"]
        if norm_name(name) in in_deck or norm_name(name.split(" // ")[0]) in in_deck:
            filtered["in_deck"] += 1
            return
        legal = (card.get("legalities") or {}).get("commander", card.get("legal_commander"))
        if legal not in (None, "legal"):
            filtered["legality"] += 1
            return
        if not set(card.get("color_identity", [])) <= set(ident):
            filtered["identity"] += 1
            return
        if card.get("game_changer") and not allow_gc:
            filtered["game_changer"] += 1
            return
        price = (card.get("prices") or {}).get("usd")
        price = float(price) if price not in (None, "") else None
        is_owned = owned is not None and name in owned
        if a.budget is not None and price is not None and price > a.budget and not is_owned:
            filtered["budget"] += 1
            return
        c = cands.setdefault(name, {"name": name, "sources": [], "role_hints": [], "cmc": card.get("cmc", 0),
                                    "type_line": card.get("type_line"), "mana_cost": card.get("mana_cost"),
                                    "oracle_text": (card.get("oracle_text") or "")[:500],
                                    "price_usd": price, "edhrec_rank": card.get("edhrec_rank"),
                                    "game_changer": bool(card.get("game_changer"))})
        if source not in c["sources"]:
            c["sources"].append(source)
        for h in ([role_hint] if role_hint else []) + list(card.get("role_hints") or []):
            if h and h not in c["role_hints"]:
                c["role_hints"].append(h)
        for k in ("synergy", "inclusion_rate", "edhrec_list"):
            if card.get(k) is not None:
                c[k] = card[k]
        c.update({k: v for k, v in extra.items() if v is not None})
        if owned is not None:
            c["owned"] = is_owned
            if is_owned:
                c["owned_qty"] = owned.count(name)
        roles, flags = card_roles(card)
        c["roles_rule"] = {k: tag_roles._bucket(v) for k, v in roles.items() if k != "land"}
        c["flags"] = sorted(f for f in flags if not f.startswith("_"))

    # owned card data, loaded up front so Spellbook / --extra names the user owns resolve even offline
    owned_cards, owned_unresolved, owned_names = [], [], []
    if owned is not None:
        owned_names = [n for n in owned.names
                       if norm_name(n) not in in_deck and norm_name(n.split(" // ")[0]) not in in_deck]
        if a.collection_cards:
            supplied = load_json(a.collection_cards)
            owned_cards = expand_cards(supplied)
            # the snippet already dropped off-identity / illegal / in-deck cards; only its not_found are unresolved
            owned_unresolved = list(supplied.get("not_found", [])) if isinstance(supplied, dict) else []
        else:
            owned_cards, owned_unresolved = resolve_collection(owned_names, a.offline)
    owned_by_name = {}
    for c in owned_cards:
        for k in (c["name"], c["name"].split(" // ")[0]):
            owned_by_name[norm_name(k)] = c

    def known(names_: list[str]) -> dict[str, dict]:
        """resolve_names, falling back to the collection's card data."""
        got = resolve_names(names_, a.offline)
        for n in names_:
            if n not in got and norm_name(n) in owned_by_name:
                got[n] = owned_by_name[norm_name(n)]
        return got

    # 1. EDHREC: saved file first, then live
    deck_stats = {}
    if a.edhrec_json:
        ed = load_json(a.edhrec_json)
        if isinstance(ed, dict) and "rows" in ed:            # browser snippet output
            deck_stats = ed.get("deck_card_stats", {})
            for card in expand_cards(ed):
                add(card, "edhrec")
            notes.append(f"EDHREC (saved, slug {ed.get('slug')}): {len(ed['rows'])} candidates with card data, "
                         f"{len(deck_stats)} deck cards with stats.")
        else:                                                # raw commander page
            stats = walk_edhrec(ed)
            deck_stats = {c["name"]: stats[c["name"]] for c in deck["cards"] if c["name"] in stats}
            top = [n for n, v in sorted(stats.items(), key=lambda kv: -((kv[1]["synergy"] or 0) * 2 + (kv[1]["inclusion_rate"] or 0)))
                   if norm_name(n) not in in_deck][:80]
            data = resolve_names(top, a.offline)
            for n in top:
                if n in data:
                    add({**data[n], **{k: v for k, v in stats[n].items() if k != "list"}, "edhrec_list": stats[n]["list"]}, "edhrec")
            if len(data) < len(top):
                notes.append(f"EDHREC page saved but {len(top) - len(data)} candidate names had no card data; use "
                             "scripts/browser/edhrec_candidates.js, which fetches card data in the same run.")
    elif not a.offline:
        slug = edhrec_slug(deck["commanders"])
        url = f"https://json.edhrec.com/pages/commanders/{slug}.json"
        try:
            data = cache_get("edhrec", url, 86400)
            if data is None:
                data = http(url)
                cache_put("edhrec", url, data)
            if data.get("__http_status") == 404:
                notes.append(f"EDHREC has no page for slug '{slug}'.")
            else:
                stats = walk_edhrec(data)
                deck_stats = {c["name"]: stats[c["name"]] for c in deck["cards"] if c["name"] in stats}
                top = [n for n, v in sorted(stats.items(), key=lambda kv: -((kv[1]["synergy"] or 0) * 2 + (kv[1]["inclusion_rate"] or 0)))
                       if norm_name(n) not in in_deck][:80]
                found = resolve_names(top, False)
                for n in top:
                    if n in found:
                        add({**found[n], "synergy": stats[n]["synergy"], "inclusion_rate": stats[n]["inclusion_rate"],
                             "edhrec_list": stats[n]["list"]}, "edhrec")
        except NetworkUnavailable as e:
            notes.append(f"EDHREC unreachable ({e}). Save it with scripts/browser/edhrec_candidates.js and pass --edhrec-json.")
        except Exception as e:  # undocumented endpoint: shape may change
            notes.append(f"EDHREC parse failed ({type(e).__name__}: {e}); skipped.")

    # 2. role gaps -> Scryfall queries (live, or printed for the model / browser snippet)
    gaps = [r for r in st["role_table"] if r.get("min") is not None and r["role"] != "land"
            and (r["status"] == "low" or (isinstance(r["target"], (int, float)) and r["have"] < r["target"]))]
    base = f"id<={ident} legal:commander -is:digital"
    if not allow_gc:
        base += " -is:gamechanger"
    if a.budget is not None:
        base += f" usd<={a.budget:g}"
    queries = {}
    for r in gaps:
        if r["role"] in ROLE_QUERIES:
            queries[r["role"]] = {"query": f"{ROLE_QUERIES[r['role']]} {base}", "have": r["have"], "target": r["target"],
                                  "min": r["min"], "status": r["status"]}
    for hint, q in STRATEGY_QUERIES.get(strategy, []):
        queries[hint] = {"query": f"{q} {base}", "have": None, "target": None, "min": None, "status": "strategy"}
    if not a.offline:
        for role, q in queries.items():
            try:
                for card in scryfall_search(q["query"], a.per_role):
                    add(card, "scryfall", role)
            except NetworkUnavailable as e:
                notes.append(f"Scryfall search unreachable ({e}).")
                break

    # 3. supplied candidates
    if a.candidates_json:
        supplied = expand_cards(load_json(a.candidates_json))
        for card in supplied:
            add(card, "supplied", card.get("role_hint"))
        notes.append(f"{len(supplied)} supplied candidate(s) read from {a.candidates_json}.")

    # 4. Spellbook near-combos
    if a.combos and os.path.exists(a.combos):
        combos = load_json(a.combos)
        if a.bracket and a.bracket <= 2:
            notes.append("Bracket <= 2: combo-completing cards not suggested.")
        else:
            missing = list(combos.get("single_card_unlocks", {}))
            data = known(missing)
            for n in missing:
                if n in data:
                    add(data[n], "spellbook", None, completes=combos["single_card_unlocks"][n])
            if len(data) < len(missing):
                lack = [n for n in missing if n not in data]
                notes.append(f"{len(lack)} combo-completing card(s) have no card data offline: " + ", ".join(lack[:8]))

    # 5. model-supplied names
    if a.extra:
        names = load_json(a.extra)
        data = known(names)
        for n in names:
            if n in data:
                add(data[n], "model", None)
            else:
                notes.append(f"extra candidate {n!r} could not be resolved")

    # 6. the collection itself: every owned card that fits the deck is a candidate
    coll_summary = None
    if owned is not None:
        names, cards, unresolved = owned_names, owned_cards, owned_unresolved
        before = len(cands)
        for card in cards:
            add(card, "collection")
        owned_cands = sum(1 for c in cands.values() if c.get("owned"))
        coll_summary = {"mode": a.collection_mode, "distinct_owned": len(owned), "not_in_deck": len(names),
                        "with_card_data": len(cards), "unresolved": unresolved[:50], "unresolved_count": len(unresolved),
                        "new_candidates_from_collection": len(cands) - before, "owned_candidates": owned_cands}
        deck_main = [c["name"] for c in deck["cards"] if c["board"] in ("main", "commander")
                     and not ("Basic" in (c["card"].get("type_line") or ""))]
        coll_summary["deck_cards_not_owned"] = sorted(n for n in deck_main if n not in owned)
        if names and not cards:
            notes.append(
                f"No card data for the {len(names)} owned cards (Scryfall unreachable and no local index). Run "
                "`python scripts/collection.py to-js <collection> --deck deck.json`, run its lines in a browser tab, "
                "then scripts/browser/collection_cards.js, join the chunks and pass --collection-cards. "
                "Until then the collection only marks which of the other candidates are owned.")
        elif unresolved:
            notes.append(f"{len(unresolved)} owned name(s) not found on Scryfall (typos or digital-only), e.g. "
                         + ", ".join(unresolved[:5]))
        if a.collection_mode == "only":
            dropped = [n for n, c in cands.items() if not c.get("owned")]
            for n in dropped:
                del cands[n]
            coll_summary["dropped_not_owned"] = len(dropped)
            notes.append(f"Collection-only mode: kept {len(cands)} owned candidate(s), dropped {len(dropped)} you don't own.")
        else:
            notes.append(f"{owned_cands} candidate(s) are in the collection ({len(cands) - before} came from it directly).")

    out = {"schema": "edh-candidates/1", "identity": ident, "bracket": a.bracket, "budget_usd": a.budget,
           "strategy": strategy, "game_changers_in_deck": gc_in_deck,
           "game_changer_cap": gc_cap if gc_cap < 99 else None,
           "under_target_roles": [r["role"] for r in gaps], "queries": queries, "filtered_out": filtered,
           "deck_card_stats": deck_stats, "candidates": list(cands.values()), "notes": notes,
           "collection": coll_summary,
           "price_note": "Scryfall prices (TCGplayer USD), refreshed daily; treat as estimates."}
    dump_json(out, a.out)
    srcs = sorted({s for c in cands.values() for s in c["sources"]})
    print(f"{len(cands)} candidates from {srcs or 'no source'}; under-target roles: {[r['role'] for r in gaps]}",
          file=sys.stderr)
    for n in notes:
        print("  - " + n, file=sys.stderr)
    if not cands or not srcs or srcs == ["spellbook"]:
        print("\nNo live or saved candidate source. Fetch candidates per gap with these Scryfall queries "
              "(scryfall.com/search, or paste into scripts/browser/scryfall_search.js):", file=sys.stderr)
        for role, q in queries.items():
            gap = f"have {q['have']:g}, target {q['target']}" if q["have"] is not None else "strategy search"
            print(f"  {role:22} ({gap}): {q['query']}", file=sys.stderr)
        print("\nwindow.QUERIES = " + json.dumps({k: v["query"] for k, v in queries.items()}) + ";", file=sys.stderr)
        print("Then rerun with --candidates-json <joined snippet output>, or --extra names.json from your own knowledge.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
