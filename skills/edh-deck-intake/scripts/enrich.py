#!/usr/bin/env python3
"""Resolve parsed decklist entries to Scryfall cards and write the canonical deck.json.

Resolution order for each name:
  1. local slim index (scryfall_data.py update) - no network, has oracle tags
  2. POST /cards/collection in batches of 75 (2 req/s)
  3. GET /cards/named?fuzzy= for anything still missing -> offered as a suggestion,
     NOT silently accepted (unless --accept-fuzzy)
  4. --cards-json: card data supplied from outside (offline / blocked-network fallback). Accepts the
     compact table from scripts/browser/cards_scryfall.js, {"cards": [...]}, or a plain list of
     Scryfall-shaped or slim cards (see edh_common.slim_card for the slim schema). Their `otags` are kept.

Usage:
  python enrich.py parsed.json -o deck.json [--accept-fuzzy] [--no-api] [--cards-json extra.json]

deck.json schema ("edh-deck/1"):
  {schema, generated_at, data: {index_built_at, price_source, price_date},
   commanders: [names], companion: name|null, color_identity: "WUBRG" subset,
   cards: [{oracle_id, name, qty, board, is_commander, is_companion, set, cn, finish,
            user_tags, card: {slim scryfall fields}, otags: [...]}],
   unresolved: [{name, line_no, suggestion}], warnings: [...], counts: {...}}
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from edh_common import NetworkUnavailable, dump_json, expand_cards, http, load_json, norm_name  # noqa: E402
import scryfall_data as sd  # noqa: E402

WUBRG = "WUBRG"
BASICS = {"plains", "island", "swamp", "mountain", "forest", "wastes",
          "snow-covered plains", "snow-covered island", "snow-covered swamp",
          "snow-covered mountain", "snow-covered forest", "snow-covered wastes"}
ANY_NUMBER_RE = re.compile(r"A deck can have any number of cards named|A deck can have up to \w+ cards named", re.I)


def _lookup_local(idx: dict, name: str) -> dict | None:
    k = norm_name(name)
    oid = idx["names"].get(k)
    if not oid and " // " in k:
        oid = idx["names"].get(k.split(" // ")[0])
    return idx["cards"].get(oid) if oid else None


def _api_collection(names: list[str]) -> tuple[dict[str, dict], list[str]]:
    found: dict[str, dict] = {}
    missing: list[str] = []
    for i in range(0, len(names), 75):
        chunk = names[i:i + 75]
        res = http("https://api.scryfall.com/cards/collection", method="POST",
                   body={"identifiers": [{"name": n} for n in chunk]})
        returned = [sd.slim(c) for c in res.get("data", [])]
        by_key = {}
        for c in returned:
            for k in [c["name"]] + [f["name"] for f in c.get("card_faces", [])]:
                by_key[norm_name(k)] = c
        for n in chunk:
            c = by_key.get(norm_name(n)) or by_key.get(norm_name(n).split(" // ")[0])
            if c:
                found[n] = c
            else:
                missing.append(n)
    return found, missing


def _api_fuzzy(name: str) -> dict | None:
    import urllib.parse
    res = http("https://api.scryfall.com/cards/named?fuzzy=" + urllib.parse.quote(name))
    if res.get("object") == "card":
        return sd.slim(res)
    return None


def enrich(parsed: dict, accept_fuzzy: bool = False, use_api: bool = True,
           extra_cards: list[dict] | None = None) -> dict:
    idx = sd.load_index()
    warnings = list(parsed.get("warnings", []))
    if idx is None and not extra_cards:
        warnings.append("No local Scryfall index; used the API (no oracle tags available - "
                        "role tagging will rely on oracle-text rules).")
    elif idx is not None and (sd.index_age_days() or 0) > sd.MAX_AGE_DAYS:
        warnings.append(f"Local Scryfall index is {sd.index_age_days():.0f} days old; run scryfall_data.py update.")

    extra = {}
    for s in extra_cards or []:
        s.setdefault("legal_commander", (s.get("legalities") or {}).get("commander", "unknown"))
        for k in [s["name"]] + [f["name"] for f in s.get("card_faces", [])]:
            extra[norm_name(k)] = s

    entries = [e for e in parsed["entries"] if e["board"] in ("main", "commander", "companion", "sideboard", "maybeboard")]
    resolved: dict[str, dict] = {}
    pending: list[str] = []
    for e in entries:
        n = e["name"]
        if n in resolved:
            continue
        c = extra.get(norm_name(n)) or extra.get(norm_name(n).split(" // ")[0])
        if not c and idx:
            c = _lookup_local(idx, n)
        if c:
            resolved[n] = c
        else:
            pending.append(n)

    suggestions: dict[str, str] = {}
    if pending and use_api:
        try:
            found, missing = _api_collection(pending)
            resolved.update(found)
            for n in missing:
                fz = _api_fuzzy(n)
                if fz and accept_fuzzy:
                    resolved[n] = fz
                    warnings.append(f"Fuzzy-matched {n!r} -> {fz['name']!r}")
                elif fz:
                    suggestions[n] = fz["name"]
            pending = [n for n in pending if n not in resolved]
        except NetworkUnavailable as ex:
            warnings.append(f"Scryfall unreachable ({ex}). Unresolved cards need --cards-json or a local index.")

    # offline "did you mean": closest names in the local index
    if idx:
        import difflib
        keys = list(idx["names"])
        for n in pending:
            if n in suggestions or n in resolved:
                continue
            base = re.sub(r"^A-", "", n)
            hit = difflib.get_close_matches(norm_name(base), keys, n=1, cutoff=0.8)
            if hit:
                suggestions[n] = idx["cards"][idx["names"][hit[0]]]["name"]

    cards, unresolved, skipped_maybe = [], [], 0
    for e in entries:
        c = resolved.get(e["name"])
        if not c and e["board"] == "maybeboard":
            skipped_maybe += 1  # maybeboard cards are optional; don't block analysis on them
            continue
        if not c:
            u = {"name": e["name"], "line_no": e.get("line_no", 0), "suggestion": suggestions.get(e["name"])}
            if e["name"].startswith("A-"):
                u["note"] = ("Alchemy (A-) rebalanced card: digital-only, not legal in paper Commander. "
                             "The suggestion is the paper original, which plays differently.")
            unresolved.append(u)
            continue
        cards.append({
            "oracle_id": c.get("oracle_id"), "name": c["name"], "qty": e["qty"], "board": e["board"],
            "is_commander": e["board"] == "commander", "is_companion": e["board"] == "companion",
            "set": e.get("set"), "cn": e.get("cn"), "finish": e.get("finish"),
            "user_tags": e.get("tags", []), "otags": c.get("otags", []),
            "card": {k: v for k, v in c.items() if k != "otags"},
        })

    # merge duplicate lines of the same card on the same board
    merged: dict[tuple, dict] = {}
    for c in cards:
        key = (c["oracle_id"], c["board"])
        if key in merged:
            merged[key]["qty"] += c["qty"]
        else:
            merged[key] = c
    cards = list(merged.values())

    commanders = [c for c in cards if c["is_commander"]]
    ci = set()
    for c in commanders:
        ci |= set(c["card"].get("color_identity", []))
    identity = "".join(x for x in WUBRG if x in ci)

    # legality checks
    in_deck = [c for c in cards if c["board"] in ("main", "commander")]
    for c in in_deck:
        card = c["card"]
        legal = card.get("legal_commander")
        if legal in ("banned", "not_legal"):
            warnings.append(f"{c['name']} is {legal.replace('_', ' ')} in Commander.")
        if card.get("digital") or c["name"].startswith("A-"):
            warnings.append(f"{c['name']} is a digital/Alchemy card and not legal in paper Commander.")
        if commanders and not set(card.get("color_identity", [])) <= ci:
            warnings.append(f"{c['name']} ({''.join(card.get('color_identity', []))}) is outside the "
                            f"commander's color identity ({identity or 'colorless'}).")
        if (c["qty"] > 1 and norm_name(c["name"]) not in BASICS
                and not ANY_NUMBER_RE.search(card.get("oracle_text", ""))):
            warnings.append(f"{c['name']} appears {c['qty']} times; Commander is singleton.")
    if commanders:
        for c in commanders:
            tl = c["card"].get("type_line", "")
            txt = c["card"].get("oracle_text", "") + " ".join(
                f.get("oracle_text", "") for f in c["card"].get("card_faces", []))
            if not (("Legendary" in tl and ("Creature" in tl or "Vehicle" in tl or "Spacecraft" in tl))
                    or "can be your commander" in txt):
                warnings.append(f"{c['name']} does not look like a legal commander; check partner/background rules.")
        if len(commanders) == 2:
            txt = " ".join(c["card"].get("oracle_text", "") for c in commanders)
            if not re.search(r"Partner|Friends forever|Choose a Background|Doctor's companion", txt):
                warnings.append("Two commanders without an obvious Partner/Background/Doctor pairing; check legality.")
    if unresolved:
        warnings.append(f"{len(unresolved)} card name(s) could not be resolved; fix them before analysis.")
    if skipped_maybe:
        warnings.append(f"{skipped_maybe} maybeboard card(s) had no card data and were left out.")

    counts = {
        "main_and_commander": sum(c["qty"] for c in in_deck),
        "lands": sum(c["qty"] for c in in_deck if "Land" in (c["card"].get("type_line", "").split(" // ")[0])),
        "unresolved": len(unresolved),
    }
    meta = (idx or {}).get("meta", {})
    return {
        "schema": "edh-deck/1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"format_guess": parsed.get("format_guess"), "url": parsed.get("url")},
        "data": {"index_built_at": meta.get("built_at"),
                 "price_source": "Scryfall (TCGplayer USD / Cardmarket EUR)",
                 "price_date": meta.get("built_at") or datetime.now(timezone.utc).date().isoformat(),
                 "has_otags": bool(meta.get("n_tagged")) or any(c.get("otags") for c in cards),
                 "card_source": "cards-json" if extra_cards else ("local index" if idx else "Scryfall API")},
        "commanders": [c["name"] for c in commanders],
        "companion": next((c["name"] for c in cards if c["is_companion"]), None),
        "color_identity": identity,
        "cards": cards,
        "unresolved": unresolved,
        "warnings": warnings,
        "counts": counts,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parsed")
    ap.add_argument("-o", "--out", default="deck.json")
    ap.add_argument("--accept-fuzzy", action="store_true")
    ap.add_argument("--no-api", action="store_true")
    ap.add_argument("--cards-json", help="JSON list of Scryfall-shaped card objects (offline fallback)")
    a = ap.parse_args()
    extra = expand_cards(load_json(a.cards_json)) if a.cards_json else None
    deck = enrich(load_json(a.parsed), a.accept_fuzzy, not a.no_api, extra)
    dump_json(deck, a.out)
    c = deck["counts"]
    print(f"{len(deck['cards'])} unique cards resolved; deck size {c['main_and_commander']}, "
          f"{c['lands']} lands, {c['unresolved']} unresolved; commander(s): {', '.join(deck['commanders']) or 'NONE'} "
          f"[{deck['color_identity'] or 'C'}]", file=sys.stderr)
    for w in deck["warnings"]:
        print("  - " + w, file=sys.stderr)
    for u in deck["unresolved"]:
        print(f"  ? {u['name']}" + (f"  (did you mean {u['suggestion']}?)" if u["suggestion"] else "")
              + (f"  [{u['note']}]" if u.get("note") else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
