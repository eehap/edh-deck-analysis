#!/usr/bin/env python3
"""Fetch a decklist from a URL and emit the same structure as parse_decklist.py.

Order of attempts:
  1. Commander Spellbook GET /card-list-from-url (official; parses Moxfield, Archidekt,
     Deckstats, TappedOut). Spellbook absorbs the scraping risk, so try it first.
  2. Direct JSON, unofficial and liable to break:
       Moxfield  https://api2.moxfield.com/v3/decks/all/{publicId}   (~1 req/s, Cloudflare)
       Archidekt https://archidekt.com/api/decks/{id}/               (skip rows with deletedAt)
If everything fails (private deck, or a sandbox proxy that blocks these hosts), either ask the user to paste
the list (Moxfield: More > Export > Copy for Moxfield; Archidekt: Export > Text) or use the browser snippet
scripts/browser/moxfield_deck.js, which runs on the deck page itself (references/browser_fetch.md).

Usage: python fetch_deck_url.py <url> [-o parsed.json]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from edh_common import NetworkUnavailable, cache_get, cache_put, dump_json, http  # noqa: E402

SPELLBOOK = "https://backend.commanderspellbook.com"


def _entry(name, qty=1, board="main", set_code=None, cn=None, finish="nonfoil", tags=None):
    return {"qty": int(qty or 1), "name": name, "board": board, "set": (set_code or None) and set_code.lower(),
            "cn": cn, "finish": finish or "nonfoil", "tags": tags or [], "line_no": 0, "raw": "(url)"}


def via_spellbook(url: str) -> list[dict]:
    res = http(f"{SPELLBOOK}/card-list-from-url?url=" + urllib.parse.quote(url, safe=""))
    if res.get("__http_status") == 404 or not res:
        raise RuntimeError("Spellbook could not read that URL")
    out = []
    for key, board in (("commanders", "commander"), ("main", "main")):
        for c in res.get(key, []) or []:
            name = c.get("card") if isinstance(c.get("card"), str) else (c.get("card") or {}).get("name")
            if name:
                out.append(_entry(name, c.get("quantity", 1), board))
    if not out:
        raise RuntimeError(f"Spellbook returned no cards (keys: {list(res)[:8]})")
    return out


def via_moxfield(url: str) -> list[dict]:
    m = re.search(r"moxfield\.com/decks/([A-Za-z0-9_\-]+)", url)
    if not m:
        raise ValueError("not a Moxfield deck URL")
    res = http(f"https://api2.moxfield.com/v3/decks/all/{m.group(1)}")
    boards = res.get("boards") or {k: res.get(k) for k in ("mainboard", "commanders", "companions", "sideboard", "maybeboard")}
    mapping = {"mainboard": "main", "commanders": "commander", "companions": "companion",
               "sideboard": "sideboard", "maybeboard": "maybeboard"}
    out = []
    for bname, board in mapping.items():
        b = boards.get(bname) or {}
        cards = b.get("cards", b) if isinstance(b, dict) else {}
        for v in (cards.values() if isinstance(cards, dict) else cards):
            card = v.get("card", {})
            out.append(_entry(card.get("name"), v.get("quantity", 1), board, card.get("set"),
                              card.get("cn"), v.get("finish")))
    if not out:
        raise RuntimeError("Moxfield returned no cards (deck private or API changed)")
    return out


def via_archidekt(url: str) -> list[dict]:
    m = re.search(r"archidekt\.com/(?:api/)?decks/(\d+)", url)
    if not m:
        raise ValueError("not an Archidekt deck URL")
    res = http(f"https://archidekt.com/api/decks/{m.group(1)}/")
    out = []
    for row in res.get("cards", []):
        if row.get("deletedAt"):
            continue
        card = row.get("card", {})
        name = (card.get("oracleCard") or {}).get("name") or card.get("name")
        cats = [c if isinstance(c, str) else c.get("name", "") for c in row.get("categories") or []]
        low = {c.lower() for c in cats}
        board = ("commander" if "commander" in low else "maybeboard" if "maybeboard" in low
                 else "sideboard" if "sideboard" in low else "companion" if "companion" in low else "main")
        out.append(_entry(name, row.get("quantity", 1), board, (card.get("edition") or {}).get("editioncode"),
                          card.get("collectorNumber"), row.get("modifier", "nonfoil").lower(), cats))
    if not out:
        raise RuntimeError("Archidekt returned no cards")
    return out


def fetch(url: str) -> dict:
    cached = cache_get("deck_urls", url, max_age_s=3600)
    if cached:
        return cached
    errors = []
    attempts = [("spellbook", via_spellbook)]
    if "moxfield.com" in url:
        attempts.append(("moxfield", via_moxfield))
    if "archidekt.com" in url:
        attempts.append(("archidekt", via_archidekt))
    for label, fn in attempts:
        try:
            entries = fn(url)
            res = {"format_guess": f"url:{label}", "url": url, "entries": entries, "warnings": []}
            if label != "spellbook":
                res["warnings"].append(f"Fetched via unofficial {label} JSON endpoint; may break without notice.")
            total = sum(e["qty"] for e in entries if e["board"] in ("main", "commander"))
            if total != 100:
                res["warnings"].append(f"Main deck + commander(s) = {total} cards.")
            if not any(e["board"] == "commander" for e in entries):
                res["warnings"].append("No commander identified; ask the user.")
            cache_put("deck_urls", url, res)
            return res
        except (NetworkUnavailable, RuntimeError, ValueError, KeyError, AttributeError) as e:
            errors.append(f"{label}: {e}")
    raise SystemExit("Could not fetch the deck:\n  " + "\n  ".join(errors) +
                     "\nOptions: ask the user to paste the export text, or (if a browser is available) open the deck "
                     "page and run scripts/browser/moxfield_deck.js there, then pass the joined result as parsed.json "
                     "(see references/browser_fetch.md).")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("-o", "--out", default="-")
    a = ap.parse_args()
    dump_json(fetch(a.url), a.out)


if __name__ == "__main__":
    main()
