#!/usr/bin/env python3
"""OKF v0.1 conformance for the lab-automation-twin bundle (the criteria normative-admissibility's validator uses):
every concept has YAML frontmatter with type/title/description/source/maturity/status/timestamp, a modality tag
(✅ / 🔧 / ❓), index.md and log.md exist, and internal .md links resolve (an error here, not a warning)."""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "L1-okf-knowledge-base" / "bundle"
FM = re.compile(r"^---\s*\n(.*?\n)---\s*\n?(.*)$", re.S)
LINK = re.compile(r"\[[^\]]*\]\(([^)]+\.md)\)")
REQ = ("type", "title", "description", "source", "maturity", "status", "timestamp")
errors = []
for name in ("index.md", "log.md"):
    if not (BUNDLE / name).is_file():
        errors.append(f"{name}: missing")
concepts = sorted((BUNDLE / "concepts").glob("*.md"))
for p in sorted(BUNDLE.rglob("*.md")):
    t = p.read_text()
    m = FM.match(t)
    if not m:
        errors.append(f"{p.relative_to(BUNDLE)}: no frontmatter")
        continue
    fm = yaml.safe_load(m.group(1)) or {}
    if p in concepts:
        errors += [f"{p.name}: `{k}` missing" for k in REQ if not fm.get(k)]
        if not any(x in m.group(2) for x in ("✅", "🔧", "❓")):
            errors.append(f"{p.name}: no modality tag")
    for tgt in LINK.findall(t):
        if not (p.parent / tgt).resolve().exists():
            errors.append(f"{p.relative_to(BUNDLE)}: dead link {tgt}")
if errors:
    print("\n".join(errors[:40]))
    print(f"validate: FAIL — {len(errors)} errors")
    sys.exit(1)
print(f"validate: PASS — {len(concepts)} concept cards: frontmatter, modality tags, links (index + log present)")
