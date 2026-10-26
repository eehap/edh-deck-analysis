#!/usr/bin/env python3
"""Read a card collection (what the user owns) for the cut/add recommender.

Accepted inputs (detected automatically):
  CSV exports, header-driven, so column order doesn't matter:
    name column:     "Name", "Card Name", "Card", "Simple Name" (TCGplayer; preferred over "Name")
    quantity column: "Count", "Quantity", "Qty", "Amount"   (missing -> 1 per row)
    Known layouts: Moxfield collection (Count, Tradelist Count, Name, Edition, ...), ManaBox (Name, Set code, ...,
    Quantity, ...), Deckbox (Count, Tradelist Count, Name, ...), Dragon Shield ("sep=," line, then Folder Name,
    Quantity, ..., Card Name, ...), TCGplayer app (Quantity, Name, Simple Name, ...), Archidekt and most others.
    A leading "sep=," / "sep=;" line and ; or tab delimiters are handled.
  Plain text: one card per line, "4 Sol Ring", "1x Sol Ring (CMM) 400 *F*", "Sol Ring" (qty 1), with or
    without section headers - the same lines a decklist export uses.
  collection.json written by this script (re-read as is).

Quantities of the same card across printings, foils and folders are summed. Names are matched like deck
names (accents, quotes, "Front // Back" or front face only). Basic lands are ignored.

Usage:
  python collection.py parse my_collection.csv -o collection.json
  python collection.py to-js collection.json --deck deck.json [--max-bytes 20000]
      prints window.COLLECTION parts for scripts/browser/collection_cards.js (names only; cards already
      in the deck and basics left out), for when the sandbox can't reach Scryfall.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from edh_common import dump_json, load_json, norm_name  # noqa: E402

NAME_COLS = ("simple name", "card name", "name", "card", "card_name", "cardname")
QTY_COLS = ("quantity", "count", "qty", "amount", "number", "copies")
BASICS = {"plains", "island", "swamp", "mountain", "forest", "wastes"}
LINE_RE = re.compile(r"^\s*(?:(\d+)\s*[xX]?\s+|[xX](\d+)\s+)?(.+?)\s*$")
HEADER_RE = re.compile(r"^\s*(//|#)|^\s*(commander|companion|deck|main(board)?|sideboard|maybeboard|collection|"
                       r"binder|tokens?|lands?|creatures?|instants?|sorcer(y|ies)|artifacts?|enchantments?|"
                       r"planeswalkers?)\s*:?\s*(\(\d+\))?\s*$", re.I)


def is_basic(name: str) -> bool:
    n = norm_name(name)
    return n in BASICS or n.startswith("snow-covered ") and n[len("snow-covered "):] in BASICS


def _clean_name(raw: str) -> str:
    s = raw.strip().strip('"')
    s = re.sub(r"\*[FEA]\*", "", s)
    s = re.sub(r"(?:^|\s)#!?\S+", "", s)                       # Moxfield tags
    s = re.sub(r"\[[^\]]*\]|\^[^^]*\^", "", s)                 # Archidekt categories / labels
    s = re.sub(r"\s+[\(\[][A-Za-z0-9]{2,6}[\)\]](?:\s+\S+)?\s*$", "", s)   # (SET) 123
    return re.sub(r"\s+", " ", s).strip()


def _parse_csv(text: str) -> tuple[dict, list[str], str]:
    lines = text.splitlines()
    if lines and re.match(r'^\s*"?sep=.?"?\s*$', lines[0], re.I):
        lines = lines[1:]
    body = "\n".join(lines)
    try:
        dialect = csv.Sniffer().sniff(body[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(body), dialect))
    if not rows:
        return {}, [], "csv"
    header = [h.strip().lower() for h in rows[0]]
    name_i = next((header.index(c) for c in NAME_COLS if c in header), None)
    qty_i = next((header.index(c) for c in QTY_COLS if c in header), None)
    if name_i is None:
        raise ValueError(f"CSV has no recognisable card-name column (header: {rows[0][:8]})")
    fmt = ("moxfield/deckbox" if "tradelist count" in header else "manabox" if "manabox id" in header
           else "dragonshield" if "folder name" in header else "tcgplayer" if "simple name" in header else "csv")
    owned, bad = {}, []
    for i, r in enumerate(rows[1:], 2):
        if len(r) <= name_i or not r[name_i].strip():
            continue
        name = _clean_name(r[name_i])
        q = 1
        if qty_i is not None and len(r) > qty_i and r[qty_i].strip():
            try:
                q = int(float(r[qty_i]))
            except ValueError:
                bad.append(f"row {i}: quantity {r[qty_i]!r}")
                continue
        if q > 0 and name:
            owned[name] = owned.get(name, 0) + q
    return owned, bad, fmt


def _parse_text(text: str) -> tuple[dict, list[str]]:
    owned, bad = {}, []
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip() or HEADER_RE.match(line):
            continue
        m = LINE_RE.match(line)
        if not m:
            bad.append(f"line {i}: {line.strip()!r}")
            continue
        q = int(m.group(1) or m.group(2) or 1)
        name = _clean_name(m.group(3))
        if name:
            owned[name] = owned.get(name, 0) + q
    return owned, bad


def parse(path: str) -> dict:
    """Return {"schema": "edh-collection/1", "format", "cards": {name: qty}, "unparsed": [...]}."""
    if path.endswith(".json"):
        obj = load_json(path)
        if isinstance(obj, dict) and obj.get("schema") == "edh-collection/1":
            return obj
        if isinstance(obj, dict) and "cards" in obj and isinstance(obj["cards"], dict):
            return {"schema": "edh-collection/1", "format": "json", "cards": obj["cards"], "unparsed": []}
        if isinstance(obj, list):        # list of names or {name, qty}
            cards = {}
            for x in obj:
                n, q = (x, 1) if isinstance(x, str) else (x.get("name"), x.get("qty") or x.get("quantity") or 1)
                if n:
                    cards[n] = cards.get(n, 0) + int(q)
            return {"schema": "edh-collection/1", "format": "json", "cards": cards, "unparsed": []}
        raise ValueError("unrecognised collection JSON")
    text = open(path, encoding="utf-8-sig").read()
    first = next((ln for ln in text.splitlines() if ln.strip() and not re.match(r'^\s*"?sep=', ln, re.I)), "")
    looks_csv = (first.count(",") >= 2 or first.count(";") >= 2 or "\t" in first) and \
        any(c in first.lower() for c in NAME_COLS)
    if looks_csv:
        owned, bad, fmt = _parse_csv(text)
    else:
        owned, bad = _parse_text(text)
        fmt = "text"
    return {"schema": "edh-collection/1", "format": fmt, "cards": owned, "unparsed": bad}


class Owned:
    """Ownership lookup that matches full names, front faces and normalized spellings."""

    def __init__(self, coll: dict):
        self.qty: dict[str, int] = {}
        for n, q in coll["cards"].items():
            for k in {norm_name(n), norm_name(n.split(" // ")[0])}:
                self.qty[k] = self.qty.get(k, 0) + q
        self.names = [n for n in coll["cards"] if not is_basic(n)]

    def count(self, name: str) -> int:
        return self.qty.get(norm_name(name)) or self.qty.get(norm_name(name.split(" // ")[0])) or 0

    def __contains__(self, name: str) -> bool:
        return self.count(name) > 0

    def __len__(self) -> int:
        return len(self.names)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("parse")
    p.add_argument("path")
    p.add_argument("-o", "--out", default="collection.json")
    j = sub.add_parser("to-js")
    j.add_argument("path", help="collection file (any accepted format)")
    j.add_argument("--deck", help="deck.json: leave out cards already in the deck and pass the deck's identity")
    j.add_argument("--max-bytes", type=int, default=20000)
    a = ap.parse_args()
    coll = parse(a.path)
    if a.cmd == "parse":
        dump_json(coll, a.out)
        print(f"{len(coll['cards'])} distinct cards, {sum(coll['cards'].values())} copies ({coll['format']}); "
              f"{len(coll['unparsed'])} unparsed", file=sys.stderr)
        for b in coll["unparsed"][:10]:
            print("  ? " + b, file=sys.stderr)
        return
    names = [n for n in coll["cards"] if not is_basic(n)]
    meta = {}
    if a.deck:
        deck = load_json(a.deck)
        in_deck = {norm_name(c["name"]) for c in deck["cards"]} | {norm_name(c["name"].split(" // ")[0]) for c in deck["cards"]}
        names = [n for n in names if norm_name(n) not in in_deck and norm_name(n.split(" // ")[0]) not in in_deck]
        meta = {"identity": deck.get("color_identity", "")}
    parts, cur = [], []
    for n in sorted(names):
        cur.append(n)
        if len(json.dumps(cur, ensure_ascii=False)) > a.max_bytes:
            parts.append(cur[:-1]); cur = [n]
    if cur:
        parts.append(cur)
    print(f"// {len(names)} names in {len(parts)} part(s). Run each line in the browser tab, in order, then "
          "scripts/browser/collection_cards.js.", file=sys.stderr)
    print("window.COLLECTION = [];" + (f" window.IDENTITY = {json.dumps(meta['identity'])};" if meta else ""))
    for part in parts:
        print("window.COLLECTION.push(..." + json.dumps(part, ensure_ascii=False, separators=(",", ":")) + ");")


if __name__ == "__main__":
    main()
