#!/usr/bin/env python3
"""Build one installable .skill file (a zip archive) per skill.

A .skill file contains the skill folder at its root (edh-deck-intake/SKILL.md, ...). Test cases
(evals/) and caches are left out. Upload the results on claude.ai, or unzip them into
~/.claude/skills/ for Claude Code.

Usage:
  python tools/package_skills.py            # writes dist/<skill>.skill
  python tools/package_skills.py -o out/
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"evals", "__pycache__", ".pytest_cache"}
SKIP_FILES = {".DS_Store"}


def check(skill: Path) -> list[str]:
    errs = []
    md = skill / "SKILL.md"
    if not md.exists():
        return ["missing SKILL.md"]
    text = md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return ["SKILL.md has no frontmatter"]
    fm = m.group(1)
    name = re.search(r"^name:\s*(.+)$", fm, re.M)
    if not name or name.group(1).strip() != skill.name:
        errs.append(f"frontmatter name should be {skill.name!r}")
    if not re.search(r"^description:\s*\S", fm, re.M):
        errs.append("frontmatter has no description")
    return errs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default=str(ROOT / "dist"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    failed = False
    for skill in sorted((ROOT / "skills").iterdir()):
        if not skill.is_dir():
            continue
        errs = check(skill)
        if errs:
            print(f"{skill.name}: " + "; ".join(errs), file=sys.stderr)
            failed = True
            continue
        dest = out / f"{skill.name}.skill"
        n = 0
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(skill.rglob("*")):
                rel = f.relative_to(skill)
                if f.is_dir() or f.name in SKIP_FILES or set(rel.parts) & SKIP_DIRS:
                    continue
                z.write(f, Path(skill.name) / rel)
                n += 1
        print(f"{dest.relative_to(ROOT) if dest.is_relative_to(ROOT) else dest}: {n} files")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
