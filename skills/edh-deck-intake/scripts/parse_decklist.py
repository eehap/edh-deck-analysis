#!/usr/bin/env python3
"""Parse a Commander decklist in any common text format into structured entries.

Handles MTG Arena, Moxfield ("Copy for Moxfield"), Archidekt text, MTGO .txt,
MTGO .dek XML, TappedOut/Deckstats markers and plain "qty name" lists.
Fully offline and deterministic. Card names are NOT resolved here; that is
enrich.py's job.

Usage:
  python parse_decklist.py deck.txt [-o parsed.json]
  cat deck.txt | python parse_decklist.py - -o parsed.json
  python parse_decklist.py deck.txt --commander "Atraxa, Praetors' Voice"

Output JSON:
  {"format_guess": "...", "entries": [{qty, name, board, set, cn, finish, tags, line_no, raw}],
   "warnings": [...]}
board is one of: commander, companion, main, sideboard, maybeboard.
"""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, __import__("os").path.dirname(__file__))
from edh_common import dump_json  # noqa: E402

HEADER_MAP = {
    "commander": "commander", "commanders": "commander", "cmdr": "commander",
    "companion": "companion", "companions": "companion",
    "deck": "main", "main": "main", "mainboard": "main", "main deck": "main",
    "maindeck": "main", "edh": "main", "creatures": "main", "creature": "main",
    "lands": "main", "land": "main", "instants": "main", "instant": "main",
    "sorceries": "main", "sorcery": "main", "artifacts": "main", "artifact": "main",
    "enchantments": "main", "enchantment": "main", "planeswalkers": "main",
    "planeswalker": "main", "battles": "main", "spells": "main", "other": "main",
    "sideboard": "sideboard", "side": "sideboard", "sb": "sideboard",
    "maybeboard": "maybeboard", "maybe": "maybeboard", "considering": "maybeboard",
    "tokens": "skip", "about": "skip", "attractions": "skip", "stickers": "skip",
}

# Archidekt categories that move a card off the main board
CATEGORY_BOARD = {"commander": "commander", "maybeboard": "maybeboard",
                  "sideboard": "sideboard", "companion": "companion",
                  "considering": "maybeboard"}

LINE_RE = re.compile(
    r"""^\s*
    (?:(?P<qty>\d+)\s*[xX]?\s+|[xX](?P<qty2>\d+)\s+)?   # 1 / 1x / x1
    (?P<rest>.+?)\s*$""", re.X)
SET_CN_RE = re.compile(r"\s+[\(\[](?P<set>[A-Za-z0-9]{2,6})[\)\]](?:\s+(?P<cn>[A-Za-z0-9\-★\*]+?))?(?=\s|$)")
TRAILING_QTY_RE = re.compile(r"^(?P<name>.+?)\s+[xX]\s?(?P<qty>\d+)$")


def _header(line: str) -> str | None:
    s = line.strip().rstrip(":").strip()
    s = re.sub(r"\s*\(\d+\)$", "", s)          # "Commander (1)"
    s = re.sub(r"^[/#]+\s*", "", s)            # "// Sideboard", "# Commander"
    key = s.lower()
    if key in HEADER_MAP:
        return HEADER_MAP[key]
    if key.startswith("name ") and not re.match(r"^\d", key):
        return "skip-line"                      # Arena "Name My Deck"
    return None


def parse_line(line: str, board: str, line_no: int) -> dict | None:
    raw = line
    s = line.strip()
    if not s or s.startswith("//"):
        return None
    if s.startswith("#") and not re.match(r"^#\s*\d", s):
        return None
    if s.upper().startswith("SB:"):            # some MTGO/forge lines
        board, s = "sideboard", s[3:].strip()

    tags: list[str] = []
    finish = "nonfoil"
    entry_board = board

    # Inline commander markers: TappedOut "*CMDR*", Deckstats "# !Commander"
    if re.search(r"\*CMDR\*|#\s*!Commander\b", s, re.I):
        entry_board = "commander"
        s = re.sub(r"\*CMDR\*|#\s*!Commander\b", "", s, flags=re.I).strip()

    # Archidekt label "^Have,#37d67a^"
    s = re.sub(r"\^[^^]*\^", "", s).strip()
    # Archidekt categories "[Ramp,Commander{top}]". An all-caps 2-6 char block
    # like "[CMM]" is a set code, not a category, and is left for SET_CN_RE.
    def _category(m: re.Match) -> str:
        block = m.group(1)
        if re.fullmatch(r"[A-Z0-9]{2,6}", block):
            return m.group(0)
        for cat in block.split(","):
            cat = re.sub(r"\{[^}]*\}", "", cat).strip()
            if cat:
                tags.append(cat)
                if cat.lower() in CATEGORY_BOARD:
                    nonlocal_board[0] = CATEGORY_BOARD[cat.lower()]
        return ""
    nonlocal_board = [entry_board]
    s = re.sub(r"\[([^\]]*)\]", _category, s).strip()
    entry_board = nonlocal_board[0]

    # Moxfield markers
    if re.search(r"\*F\*", s):
        finish = "foil"
    if re.search(r"\*E\*", s):
        finish = "etched"
    s = re.sub(r"\*[FEA]\*", "", s)
    for t in re.findall(r"(?:^|\s)#!?([^\s#]+)", s):
        tags.append(t)
    s = re.sub(r"(?:^|\s)#!?[^\s#]+", "", s).strip()

    m = LINE_RE.match(s)
    if not m:
        return None
    qty = int(m.group("qty") or m.group("qty2") or 1)
    rest = m.group("rest")
    if not (m.group("qty") or m.group("qty2")):
        tm = TRAILING_QTY_RE.match(rest)
        if tm:
            rest, qty = tm.group("name"), int(tm.group("qty"))

    set_code = cn = None
    sm = SET_CN_RE.search(" " + rest)
    if sm:
        set_code = sm.group("set").lower()
        cn = sm.group("cn")
        rest = (" " + rest)[: sm.start()].strip()
    name = re.sub(r"\s+", " ", rest).strip().strip('"')
    if not name or re.fullmatch(r"\d+", name):
        return None
    return {"qty": qty, "name": name, "board": entry_board, "set": set_code, "cn": cn,
            "finish": finish, "tags": tags, "line_no": line_no, "raw": raw.rstrip("\n")}


def parse_dek_xml(text: str) -> list[dict]:
    root = ET.fromstring(text)
    out = []
    for i, c in enumerate(root.iter("Cards")):
        out.append({"qty": int(c.get("Quantity", "1")), "name": c.get("Name", "").strip(),
                    "board": "sideboard" if c.get("Sideboard", "false").lower() == "true" else "main",
                    "set": None, "cn": None, "finish": "nonfoil", "tags": [],
                    "line_no": i + 1, "raw": ET.tostring(c, encoding="unicode").strip()})
    return out


def guess_format(text: str) -> str:
    if text.lstrip().startswith("<?xml") or "<Deck" in text[:500]:
        return "mtgo_dek"
    if re.search(r"\*[FEA]\*|#!", text):
        return "moxfield"
    if re.search(r"^\s*\d+x\s.+\[[^\]]+\]", text, re.M):
        return "archidekt"
    if re.search(r"^(Commander|Companion|Deck|Sideboard)\s*$", text, re.M) and re.search(r"\([A-Z0-9]{2,6}\)\s+\S+", text):
        return "arena"
    if re.search(r"\*CMDR\*", text, re.I):
        return "tappedout"
    if re.search(r"^\s*SIDEBOARD:?\s*$", text, re.M | re.I):
        return "mtgo_txt"
    return "plain"


def parse(text: str, commander_hint: list[str] | None = None) -> dict:
    warnings: list[str] = []
    fmt = guess_format(text)
    if fmt == "mtgo_dek":
        entries = parse_dek_xml(text)
        sections = None
    else:
        entries = []
        board = "main"
        saw_header = False
        sections: list[list[int]] = [[]]   # entry indices per blank-line block, for headerless lists
        for i, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                if sections[-1]:
                    sections.append([])
                continue
            h = _header(line)
            if h == "skip-line":
                continue
            if h:
                saw_header = True
                board = h
                continue
            if board == "skip":
                continue
            e = parse_line(line, board, i)
            if e:
                sections[-1].append(len(entries))
                entries.append(e)
            else:
                warnings.append(f"line {i}: could not parse {line.strip()!r}")
        sections = [s for s in sections if s]
        if saw_header:
            sections = None

    # Headerless or MTGO: infer commander from a small trailing block / sideboard
    has_cmdr = any(e["board"] == "commander" for e in entries)
    if not has_cmdr and fmt != "mtgo_dek" and sections and len(sections) >= 2:
        last = sections[-1]
        main_qty = sum(entries[i]["qty"] for s in sections[:-1] for i in s)
        last_qty = sum(entries[i]["qty"] for i in last)
        if 1 <= last_qty <= 2 and 96 <= main_qty + last_qty <= 101:
            for i in last:
                entries[i]["board"] = "commander"
            warnings.append("Inferred commander(s) from the final 1-2 card block; confirm with the user.")
            has_cmdr = True
        elif last_qty <= 15:
            for i in last:
                entries[i]["board"] = "sideboard"
    if not has_cmdr:
        side = [e for e in entries if e["board"] == "sideboard"]
        if 1 <= sum(e["qty"] for e in side) <= 2:
            for e in side:
                e["board"] = "commander"
            warnings.append("Treated the 1-2 card sideboard as the commander(s) (MTGO convention); confirm.")
            has_cmdr = True

    if commander_hint:
        hints = {h.lower() for h in commander_hint}
        found = False
        for e in entries:
            if e["name"].lower() in hints or e["name"].split(" // ")[0].lower() in hints:
                e["board"], found = "commander", True
        if not found:
            for h in commander_hint:
                entries.insert(0, {"qty": 1, "name": h, "board": "commander", "set": None, "cn": None,
                                   "finish": "nonfoil", "tags": [], "line_no": 0, "raw": "(from --commander)"})
        has_cmdr = True

    if not has_cmdr:
        warnings.append("No commander identified. Ask the user which card is the commander, "
                        "or rerun with --commander.")

    total = sum(e["qty"] for e in entries if e["board"] in ("main", "commander"))
    if total != 100:
        warnings.append(f"Main deck + commander(s) = {total} cards (a legal Commander deck has exactly 100).")
    return {"format_guess": fmt, "entries": entries, "warnings": warnings}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="decklist file, or - for stdin")
    ap.add_argument("-o", "--out", default="-")
    ap.add_argument("--commander", action="append", help="commander name (repeat for partners)")
    a = ap.parse_args()
    text = sys.stdin.read() if a.path == "-" else open(a.path, encoding="utf-8-sig").read()
    res = parse(text, a.commander)
    dump_json(res, a.out)
    if a.out != "-":
        n = sum(e["qty"] for e in res["entries"])
        print(f"Parsed {len(res['entries'])} lines / {n} cards as {res['format_guess']}; "
              f"{len(res['warnings'])} warning(s)", file=sys.stderr)
        for w in res["warnings"]:
            print("  - " + w, file=sys.stderr)


if __name__ == "__main__":
    main()
