"""Shared helpers for the EDH deck-analysis skills.

This file is copied verbatim into each skill's scripts/ folder so every skill
stays self-contained. If you change it, copy it to the other skills too.

Standard library only: these scripts must run in sandboxes where pip may not work.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = os.environ.get("EDH_USER_AGENT", "edh-deck-skills/1.0 (personal deck analysis)")
CACHE_DIR = Path(os.environ.get("EDH_CACHE_DIR", Path.home() / ".cache" / "edh-skills"))

# Minimum spacing per host/endpoint family, in seconds.
#  - Scryfall /cards/search, /cards/named, /cards/collection, /cards/random: 2/s  -> 0.5s
#  - Scryfall everything else: 10/s -> 0.1s (we use 0.15 for headroom)
#  - Commander Spellbook: ~80/min -> 0.75s
#  - Moxfield: concurrent requests return empty bodies; ~1/s
#  - EDHREC / Archidekt: undocumented; be polite at 1/s
_SPACING = {
    "scryfall_slow": 0.55,
    "scryfall": 0.15,
    "spellbook": 0.8,
    "moxfield": 1.1,
    "archidekt": 1.0,
    "edhrec": 1.0,
    "default": 1.0,
}
_last_call: dict[str, float] = {}


class NetworkUnavailable(RuntimeError):
    """Raised when the host cannot be reached at all (sandbox allowlist, offline)."""


def _bucket(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc
    path = urllib.parse.urlparse(url).path
    if "scryfall.com" in host:
        if re.match(r"^/cards/(search|named|collection|random)", path):
            return "scryfall_slow"
        return "scryfall"
    if "scryfall.io" in host:
        return "none"  # file hosts are not rate limited
    if "commanderspellbook" in host:
        return "spellbook"
    if "moxfield" in host:
        return "moxfield"
    if "archidekt" in host:
        return "archidekt"
    if "edhrec" in host:
        return "edhrec"
    return "default"


def _throttle(bucket: str) -> None:
    if bucket == "none":
        return
    spacing = _SPACING.get(bucket, 1.0)
    wait = _last_call.get(bucket, 0) + spacing - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call[bucket] = time.monotonic()


def http(url: str, *, method: str = "GET", body: dict | None = None,
         retries: int = 3, timeout: int = 60, raw: bool = False):
    """Polite HTTP with User-Agent, per-host throttling and 429 handling.

    Returns parsed JSON (or bytes when raw=True). Raises NetworkUnavailable when
    the host is unreachable so callers can fall back to an offline path.
    """
    bucket = _bucket(url)
    data = json.dumps(body).encode() if body is not None else None
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json;q=0.9,*/*;q=0.8",
               "Accept-Encoding": "gzip"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    last_err = None
    for attempt in range(retries + 1):
        _throttle(bucket)
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip" or payload[:2] == b"\x1f\x8b":
                    payload = gzip.decompress(payload)
                if raw:
                    return payload
                if not payload.strip():
                    raise RuntimeError(f"Empty response body from {url} (rate-limited?)")
                return json.loads(payload)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                # Scryfall locks you out for 30 s after a 429; Spellbook asks us to back off.
                retry_after = float(e.headers.get("Retry-After") or (30 if bucket.startswith("scryfall") else 10))
                print(f"[edh] 429 from {urllib.parse.urlparse(url).netloc}; waiting {retry_after:.0f}s",
                      file=sys.stderr)
                time.sleep(retry_after)
                continue
            if e.code == 404:
                try:
                    return {"__http_status": 404, **json.loads(e.read() or b"{}")}
                except Exception:
                    return {"__http_status": 404}
            if 500 <= e.code < 600 and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_err = e
            if attempt < 1:
                time.sleep(1)
                continue
            raise NetworkUnavailable(
                f"Cannot reach {urllib.parse.urlparse(url).netloc}: {e}. "
                "If you are in a sandbox, the domain may need to be allowlisted."
            ) from e
    raise RuntimeError(f"Giving up on {url}: {last_err}")


# ---------- small JSON cache ----------

def cache_path(namespace: str, key: str, suffix: str = ".json") -> Path:
    h = hashlib.sha256(key.encode()).hexdigest()[:24]
    p = CACHE_DIR / namespace / f"{h}{suffix}"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def cache_get(namespace: str, key: str, max_age_s: float):
    p = cache_path(namespace, key)
    if p.exists() and time.time() - p.stat().st_mtime < max_age_s:
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


def cache_put(namespace: str, key: str, value) -> None:
    cache_path(namespace, key).write_text(json.dumps(value))


# ---------- name normalization ----------

_QUOTES = {"‘": "'", "’": "'", "‛": "'", "′": "'", "`": "'",
           "“": '"', "”": '"', "–": "-", "—": "-"}


def norm_name(name: str) -> str:
    """Lookup key for a card name: accents stripped, quotes unified, lowercase."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    for a, b in _QUOTES.items():
        s = s.replace(a, b)
    s = re.sub(r"\s*/{1,2}\s*", " // ", s)  # "Fire/Ice", "Fire // Ice"
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def load_json(path: str | Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj, path: str | Path | None) -> None:
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    if path in (None, "-"):
        print(text)
    else:
        Path(path).write_text(text, encoding="utf-8")


def card_text(card: dict) -> str:
    """All oracle text on a card, faces joined (for role tagging)."""
    parts = []
    if card.get("oracle_text"):
        parts.append(card["oracle_text"])
    for face in card.get("card_faces") or []:
        if face.get("oracle_text"):
            parts.append(face["oracle_text"])
    return "\n".join(dict.fromkeys(parts))


def card_type_line(card: dict) -> str:
    if card.get("type_line"):
        return card["type_line"]
    return " // ".join(f.get("type_line", "") for f in card.get("card_faces") or [])


def front_face(card: dict) -> dict:
    faces = card.get("card_faces") or []
    return faces[0] if faces and card.get("layout") in ("modal_dfc", "transform", "flip", "adventure") else card


# ---------- slim card schema (shared by every skill and the browser snippets) ----------
# Required keys: oracle_id, name, layout, mana_cost, cmc, type_line, oracle_text, color_identity,
# produced_mana, legalities.commander, game_changer, prices.usd, card_faces[name, mana_cost, type_line,
# oracle_text]. Optional keys kept when present: rarity, digital, edhrec_rank, keywords, otags.
SLIM_FACE = ("name", "mana_cost", "type_line", "oracle_text")
SLIM_OPTIONAL = ("rarity", "digital", "edhrec_rank", "keywords", "otags", "flavor_name", "printed_name",
                 "games", "reserved", "power", "toughness", "loyalty")


def slim_card(c: dict) -> dict:
    """Reduce a full Scryfall card (or an already-slim one) to the slim schema."""
    out = {k: c.get(k) for k in ("oracle_id", "name", "layout", "mana_cost", "cmc", "type_line",
                                 "oracle_text", "color_identity", "produced_mana", "game_changer")}
    if not out["oracle_id"] and c.get("card_faces"):
        out["oracle_id"] = c["card_faces"][0].get("oracle_id")
    leg = c.get("legalities") or {}
    out["legalities"] = {"commander": leg.get("commander", c.get("legal_commander", "unknown"))}
    pr = c.get("prices") or {}
    out["prices"] = {"usd": pr.get("usd")}
    if c.get("card_faces"):
        out["card_faces"] = [{k: f.get(k, "") for k in SLIM_FACE} for f in c["card_faces"]]
    for k in SLIM_OPTIONAL:
        if c.get(k) is not None:
            out[k] = c[k]
    return {k: v for k, v in out.items() if v is not None}


# ---------- compact table format used by the browser snippets ----------
# {"schema": "edh-cards-table/1", "fields": [...], "rows": [[...], ...]}
# color_identity / produced_mana are strings ("WU"); card_faces is [[name, mana_cost, type_line, oracle_text], ...];
# legal_commander and usd are flattened. Extra fields (synergy, inclusion_rate, role_hint, ...) pass through.

EXTRA_FIELDS = ("synergy", "inclusion_rate", "num_decks", "potential_decks", "edhrec_list", "role_hint",
                "role_hints", "completes", "scryfall_id")


def expand_cards(obj) -> list[dict]:
    """Accept a list of cards, {"cards": [...]}, or the compact table format; return slim card dicts."""
    if isinstance(obj, dict) and "rows" in obj and "fields" in obj:
        out = []
        for row in obj["rows"]:
            r = dict(zip(obj["fields"], row))
            c = {k: v for k, v in r.items() if k not in ("legal_commander", "usd", "card_faces",
                                                         "color_identity", "produced_mana")}
            c["color_identity"] = list(r.get("color_identity") or "")
            if r.get("produced_mana"):
                c["produced_mana"] = list(r["produced_mana"])
            c["legalities"] = {"commander": r.get("legal_commander", "legal")}
            c["prices"] = {"usd": r.get("usd")}
            if r.get("card_faces"):
                c["card_faces"] = [dict(zip(SLIM_FACE, f)) for f in r["card_faces"]]
            out.append({k: v for k, v in c.items() if v is not None})
        return out
    if isinstance(obj, dict):
        obj = obj.get("cards", obj.get("candidates", obj.get("data", [])))
    res = []
    for c in obj:
        sc = slim_card(c)
        for k in EXTRA_FIELDS:
            if c.get(k) is not None:
                sc[k] = c[k]
        res.append(sc)
    return res


# ---------- CLI helpers: joining snippet chunks, printing arrays for snippets ----------

def _cli() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="EDH helper commands")
    sub = ap.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("join", help="concatenate browser-snippet chunks into one JSON file and validate it")
    j.add_argument("out")
    j.add_argument("parts", nargs="+")
    n = sub.add_parser("names-js", help="print const DECK_NAMES/COMMANDERS for pasting into a browser snippet")
    n.add_argument("deck", help="deck.json or parsed.json")
    a = ap.parse_args()
    if a.cmd == "join":
        def key(p):
            m = re.findall(r"\d+", Path(p).name)
            return (int(m[-1]) if m else 0, p)
        pieces = []
        for p in sorted(a.parts, key=key):
            raw = Path(p).read_text(encoding="utf-8").strip()
            # a chunk copied from a tool result may still be a quoted JSON string; unquote it
            if raw.startswith('"') and raw.endswith('"'):
                raw = json.loads(raw)
            pieces.append(raw)
        obj = json.loads("".join(pieces))
        Path(a.out).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        size = len(obj) if isinstance(obj, (list, dict)) else 0
        print(f"wrote {a.out}: valid JSON, {size} top-level items", file=sys.stderr)
    elif a.cmd == "names-js":
        d = load_json(a.deck)
        rows = d.get("cards") or d.get("entries") or []
        main = [{"card": r["name"], "quantity": r.get("qty", 1)} for r in rows if r.get("board") == "main"]
        cmd = [{"card": r["name"], "quantity": 1} for r in rows if r.get("board") == "commander"]
        print("window.DECK = " + json.dumps({"commanders": cmd, "main": main}, ensure_ascii=False, separators=(",", ":")) + ";")


if __name__ == "__main__":
    _cli()
