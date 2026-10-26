#!/usr/bin/env python3
"""Keep the files that are deliberately duplicated across skills identical.

Each skill must work on its own when installed, so a few files are copied into several skills.
The canonical copy lives in one skill; this script copies it to the others.

Usage:
  python tools/sync_shared.py          # copy canonical files over the duplicates
  python tools/sync_shared.py --check  # exit 1 if any duplicate differs (use in CI)
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "skills"

# canonical file -> skills that carry a copy at the same relative path
SHARED = {
    "edh-deck-intake/scripts/edh_common.py": ["edh-deck-structure", "edh-combo-finder", "edh-cut-add", "edh-deck-review"],
    "edh-deck-intake/scripts/scryfall_data.py": ["edh-cut-add"],
    "edh-deck-structure/scripts/tag_roles.py": ["edh-cut-add"],
    "edh-deck-intake/references/browser_fetch.md": ["edh-combo-finder", "edh-cut-add", "edh-deck-review"],
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    bad = 0
    for src_rel, targets in SHARED.items():
        src = ROOT / src_rel
        rel = Path(*Path(src_rel).parts[1:])
        for skill in targets:
            dst = ROOT / skill / rel
            same = dst.exists() and filecmp.cmp(src, dst, shallow=False)
            if same:
                continue
            if a.check:
                print(f"DIFFERS: {dst.relative_to(ROOT.parent)} (canonical: {src.relative_to(ROOT.parent)})")
                bad += 1
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"updated {dst.relative_to(ROOT.parent)}")
    if a.check:
        print("shared files in sync" if not bad else f"{bad} shared file(s) out of sync; run tools/sync_shared.py")
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
