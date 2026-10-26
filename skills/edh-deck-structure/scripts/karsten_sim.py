#!/usr/bin/env python3
"""Reproduce Frank Karsten's 99-card colored-source requirements by Monte Carlo.

Method (Karsten, "How Many Sources Do You Need to Consistently Cast Your Spells? A 2022 Update"):
  - 99-card deck with 41 lands, K of which make the color.
  - Commander rules: free first mulligan, and the player on the play still draws on turn 1,
    so by turn M you have seen 7 + M cards (before bottoming).
  - London mulligan: mulligan the free 7 with 0,1,2,6,7 lands; later 7s with 0,1,6,7;
    6-card keeps (one bottomed) with 0,1,5,6 lands. Bottom toward ~3 lands, off-color lands first.
  - Success: at least N colored sources by turn M, CONDITIONAL on having at least M lands by then.
  - Target: (89 + M)% -> 90% for a one-drop, 91% for a two-drop, ...
Find the smallest K meeting the target.

Usage:
  python karsten_sim.py --cost 1CC                 # one requirement
  python karsten_sim.py --cost 2C --trials 40000
  python karsten_sim.py --verify                    # compare a few table cells with the published values
  python karsten_sim.py --cost CC --lands 37        # what changes with fewer lands
  python karsten_sim.py --prob --cost CC --sources 24   # probability for a given source count
"""
from __future__ import annotations

import argparse
import random
import re

PUBLISHED = {"C": 19, "1C": 19, "2C": 18, "CC": 30, "1CC": 28, "CCC": 36, "3C": 16, "2CC": 26}


def parse_cost(cost: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d*)(C+)", cost.upper())
    if not m:
        raise ValueError("cost like C, 1C, 2CC, 3CCC")
    return int(m.group(1) or 0), len(m.group(2))


def _lands_in(hand, L):
    return sum(1 for c in hand if c < L)


def _bottom(hand: list[int], n: int, K: int, L: int) -> list[int]:
    """Bottom n cards: aim for ~3 lands, prefer bottoming off-color lands, then spells."""
    hand = sorted(hand)
    for _ in range(n):
        lands = [c for c in hand if c < L]
        if len(lands) > 3:
            off = [c for c in lands if c >= K]
            hand.remove(off[0] if off else lands[-1])
        else:
            spells = [c for c in hand if c >= L]
            hand.remove(spells[0] if spells else hand[-1])
    return hand


def trial(K: int, L: int, M: int, rng: random.Random, N: int = 99):
    # cards 0..K-1 = colored sources (lands), K..L-1 = other lands, L.. = spells
    deck = list(range(N))
    # attempt 0: free 7; 1: 7 again (free mulligan used); 2: keep 6; 3: keep 5 no matter what
    mull_if = {0: (0, 1, 2, 6, 7), 1: (0, 1, 6, 7), 2: (0, 1, 5, 6)}
    for attempt in range(4):
        rng.shuffle(deck)
        hand = deck[:7]
        bottom = max(attempt - 1, 0)
        if bottom:
            hand = _bottom(hand, bottom, K, L)
        if attempt < 3 and _lands_in(hand, L) in mull_if[attempt]:
            continue
        break
    library = deck[7:]
    seen = hand + library[:M]             # draws on turns 1..M (Commander turn-1 draw)
    lands_seen = _lands_in(seen, L)
    sources = sum(1 for c in seen if c < K)
    return lands_seen >= M, sources


def prob(K: int, L: int, M: int, need: int, trials: int, seed: int = 1) -> float:
    rng = random.Random(seed)
    ok = hit = 0
    for _ in range(trials):
        cond, s = trial(K, L, M, rng)
        if cond:
            ok += 1
            hit += s >= need
    return hit / max(ok, 1)


def min_sources(cost: str, lands: int = 41, trials: int = 20000) -> tuple[int, float]:
    generic, pips = parse_cost(cost)
    M = generic + pips
    target = (89 + M) / 100
    lo, hi = pips, lands
    best = (hi, prob(hi, lands, M, pips, trials))
    while lo <= hi:
        mid = (lo + hi) // 2
        p = prob(mid, lands, M, pips, trials)
        if p >= target:
            best = (mid, p)
            hi = mid - 1
        else:
            lo = mid + 1
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cost")
    ap.add_argument("--lands", type=int, default=41)
    ap.add_argument("--trials", type=int, default=20000)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--prob", action="store_true")
    ap.add_argument("--sources", type=int)
    a = ap.parse_args()
    if a.verify:
        for cost, pub in PUBLISHED.items():
            k, p = min_sources(cost, a.lands, a.trials)
            print(f"{cost:5} simulated {k:2}  published {pub:2}  ({p:.3f} at simulated K)")
        return
    if a.prob:
        g, pips = parse_cost(a.cost)
        print(f"{prob(a.sources, a.lands, g + pips, pips, a.trials):.3f}")
        return
    k, p = min_sources(a.cost, a.lands, a.trials)
    print(f"{a.cost}: {k} sources (P={p:.3f}, target {(89 + sum(parse_cost(a.cost))) / 100:.2f})")


if __name__ == "__main__":
    main()
