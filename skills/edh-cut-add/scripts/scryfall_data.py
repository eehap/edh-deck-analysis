#!/usr/bin/env python3
"""Scryfall bulk data: download Oracle Cards + Oracle Tags and build a slim local index.

The full Oracle Cards file is 150+ MB; loading it every run is slow and memory-hungry.
This builds ~/.cache/edh-skills/oracle_index.json.gz with only the fields the
analysis needs, plus a name index and each card's oracle tags (ancestors expanded).

Usage:
  python scryfall_data.py update            # refresh if older than 7 days
  python scryfall_data.py update --force
  python scryfall_data.py update --cards-file oracle-cards.json [--tags-file oracle-tags.json]
  python scryfall_data.py status

Scryfall guidance (docs, Oct 2026): bulk files are regenerated every ~12 h; for
gameplay data weekly or on set release is enough. Prices are "dangerously stale"
after 24 h, so price-sensitive work should refresh daily or use the API.
Data is free for community tools; do not paywall it or imply Scryfall endorsement.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from edh_common import CACHE_DIR, NetworkUnavailable, http, norm_name  # noqa: E402

INDEX_PATH = CACHE_DIR / "oracle_index.json.gz"
MAX_AGE_DAYS = 7

SLIM_FIELDS = ["oracle_id", "name", "layout", "mana_cost", "cmc", "type_line", "oracle_text",
               "keywords", "colors", "color_identity", "produced_mana", "game_changer",
               "edhrec_rank", "reserved", "digital", "rarity", "games", "power", "toughness",
               "loyalty", "flavor_name", "printed_name", "scryfall_uri"]
FACE_FIELDS = ["name", "mana_cost", "type_line", "oracle_text", "colors", "flavor_name", "printed_name"]


def slim(card: dict) -> dict:
    out = {k: card[k] for k in SLIM_FIELDS if k in card}
    out["legal_commander"] = (card.get("legalities") or {}).get("commander", "unknown")
    if card.get("prices"):
        out["prices"] = {k: card["prices"].get(k) for k in ("usd", "usd_foil", "eur", "tix")}
    if card.get("card_faces"):
        out["card_faces"] = [{k: f[k] for k in FACE_FIELDS if k in f} for f in card["card_faces"]]
    if not out.get("oracle_id") and card.get("card_faces"):
        out["oracle_id"] = card["card_faces"][0].get("oracle_id")  # reversible cards
    return out


def name_keys(card: dict) -> list[str]:
    keys = [card["name"]]
    for f in card.get("card_faces") or []:
        keys.append(f.get("name", ""))
        keys += [f.get("flavor_name") or "", f.get("printed_name") or ""]
    keys += [card.get("flavor_name") or "", card.get("printed_name") or ""]
    return [norm_name(k) for k in keys if k]


# ---------- oracle tags ----------

def parse_oracle_tags(raw) -> dict[str, list[str]]:
    """oracle_id -> sorted tag slugs, with ancestors expanded.

    The Oracle Tags bulk file schema is new (2026). This loader accepts a list of
    tag objects or {"data": [...]} and looks for: id, slug/label/name, parent_ids,
    aliases, and taggings as a list of oracle_ids or of {"oracle_id": ...} objects.
    If Scryfall changes the shape, adjust here; everything else is shape-agnostic.
    """
    tags = raw.get("data", raw.get("tags", raw)) if isinstance(raw, dict) else raw
    by_id: dict[str, dict] = {}
    for t in tags:
        if not isinstance(t, dict):
            continue
        tid = t.get("id") or t.get("uuid") or t.get("slug") or t.get("label")
        slug = (t.get("slug") or t.get("label") or t.get("name") or "").strip().lower().replace(" ", "-")
        if not tid or not slug:
            continue
        taggings = t.get("taggings") or t.get("oracle_ids") or t.get("cards") or []
        oids = []
        for x in taggings:
            if isinstance(x, str):
                oids.append(x)
            elif isinstance(x, dict):
                oid = x.get("oracle_id") or x.get("id")
                if oid:
                    oids.append(oid)
        by_id[tid] = {"slug": slug, "parents": t.get("parent_ids") or t.get("parents") or [],
                      "oids": oids}

    memo: dict[str, set[str]] = {}

    def ancestors(tid: str, seen=()) -> set[str]:
        if tid in memo:
            return memo[tid]
        out: set[str] = set()
        for p in by_id.get(tid, {}).get("parents", []):
            if p in by_id and p not in seen:
                out.add(by_id[p]["slug"])
                out |= ancestors(p, seen + (tid,))
        memo[tid] = out
        return out

    result: dict[str, set[str]] = {}
    for tid, t in by_id.items():
        full = {t["slug"]} | ancestors(tid)
        for oid in t["oids"]:
            result.setdefault(oid, set()).update(full)
    return {k: sorted(v) for k, v in result.items()}


# ---------- build / load ----------

def _download(bulk_type_matches, label: str) -> Path | None:
    """Download one bulk file. Since 2026 Scryfall's /bulk-data lists only `jsonl_download_uri`
    (gzipped JSON Lines) and `compressed_size`; older responses had `download_uri` (a JSON array)."""
    meta = http("https://api.scryfall.com/bulk-data")
    for item in meta.get("data", []):
        if bulk_type_matches(item):
            uri = item.get("jsonl_download_uri") or item.get("download_uri")
            size = item.get("compressed_size") or item.get("size") or 0
            ext = ".jsonl.gz" if uri.endswith(".jsonl.gz") else ".jsonl" if uri.endswith(".jsonl") else ".json"
            dest = CACHE_DIR / f"{item['type']}{ext}"
            print(f"[scryfall] downloading {label} ({size / 1e6:.0f} MB, updated {item.get('updated_at')})",
                  file=sys.stderr)
            data = http(uri, raw=True, timeout=600)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return dest
    print(f"[scryfall] no bulk file matching {label} in /bulk-data", file=sys.stderr)
    return None


def read_bulk(path: Path) -> list:
    """Read a bulk file as a list: JSON array or JSON Lines, optionally gzipped."""
    path = Path(path)
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8").lstrip()
    if text.startswith("["):
        return json.loads(text)
    if text.startswith("{") and not text.split("\n", 1)[0].rstrip().endswith("}"):
        obj = json.loads(text)          # single JSON object such as {"data": [...]}
        return obj.get("data", obj)
    out = []
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if line:
            out.append(json.loads(line))
    if len(out) == 1 and isinstance(out[0], dict) and "data" in out[0]:
        return out[0]["data"]
    return out


def build_index(cards_file: Path, tags_file: Path | None) -> dict:
    cards = read_bulk(cards_file)
    tags = {}
    if tags_file and Path(tags_file).exists():
        tags = parse_oracle_tags(read_bulk(tags_file))
    idx = {"cards": {}, "names": {}, "meta": {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cards_file": str(cards_file), "tags_file": str(tags_file) if tags_file else None,
        "n_cards": 0, "n_tagged": 0}}
    for c in cards:
        if c.get("layout") in ("token", "double_faced_token", "emblem", "art_series", "vanguard", "scheme", "planar"):
            continue
        s = slim(c)
        oid = s.get("oracle_id")
        if not oid:
            continue
        if oid in tags:
            s["otags"] = tags[oid]
            idx["meta"]["n_tagged"] += 1
        idx["cards"][oid] = s
        for k in name_keys(c):
            prev = idx["names"].get(k)
            # Prefer paper cards over digital-only duplicates for a shared name
            if prev is None or (idx["cards"][prev].get("digital") and not s.get("digital")):
                idx["names"][k] = oid
    idx["meta"]["n_cards"] = len(idx["cards"])
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(INDEX_PATH, "wt", encoding="utf-8") as f:
        json.dump(idx, f)
    return idx["meta"]


_INDEX = None


def load_index(required: bool = False) -> dict | None:
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    if not INDEX_PATH.exists():
        if required:
            raise FileNotFoundError(f"No local index at {INDEX_PATH}; run scryfall_data.py update")
        return None
    with gzip.open(INDEX_PATH, "rt", encoding="utf-8") as f:
        _INDEX = json.load(f)
    return _INDEX


def index_age_days() -> float | None:
    if not INDEX_PATH.exists():
        return None
    return (time.time() - INDEX_PATH.stat().st_mtime) / 86400


def update(force: bool = False, cards_file: str | None = None, tags_file: str | None = None) -> dict:
    if cards_file:
        return build_index(Path(cards_file), Path(tags_file) if tags_file else None)
    age = index_age_days()
    if not force and age is not None and age < MAX_AGE_DAYS:
        return {"skipped": True, "age_days": round(age, 2), **(load_index() or {}).get("meta", {})}
    cf = _download(lambda i: i.get("type") == "oracle_cards", "Oracle Cards")
    tf = _download(lambda i: "tag" in (i.get("type", "") + i.get("name", "")).lower()
                   and "oracle" in (i.get("type", "") + i.get("name", "")).lower(), "Oracle Tags")
    if not cf:
        raise RuntimeError("Oracle Cards bulk file not found")
    return build_index(cf, tf)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update")
    u.add_argument("--force", action="store_true")
    u.add_argument("--cards-file")
    u.add_argument("--tags-file")
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "status":
        idx = load_index()
        print(json.dumps({"index": str(INDEX_PATH), "exists": idx is not None,
                          "age_days": index_age_days(), **(idx or {}).get("meta", {})}, indent=2))
        return
    try:
        print(json.dumps(update(a.force, a.cards_file, a.tags_file), indent=2))
    except NetworkUnavailable as e:
        print(f"ERROR: {e}\nFall back to per-card API lookups or provide --cards-file.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
