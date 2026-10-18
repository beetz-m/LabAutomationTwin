#!/usr/bin/env python3
"""Outward-edge guard for lab-automation-twin (VRB three-category convention):
  1. every `grounds` target is an upstream L2 class (compiled union: AICOR + robot-scientist + VRB + normative-adm.);
  2. every L1 concept is classified exactly once (grounds | divergence | out-of-scope);
  3. every divergence carries a register tag present in DEFERRED-REGISTER.md and a `why`;
  4. every out-of-scope group names a non-empty reason;
  5. nothing under the frozen upstream trees is newer than this module's build (this repo writes nothing there)."""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
imp = yaml.safe_load((ROOT / "aicor-imports.yaml").read_text())
up = {l.strip() for l in (ROOT / "build" / "upstream-names.txt").read_text().splitlines() if l.strip()}
reg = (ROOT / "DEFERRED-REGISTER.md").read_text()
concepts = {p.stem for p in (ROOT / "L1-okf-knowledge-base" / "bundle" / "concepts").glob("*.md")}
err, seen = [], []
for c, targets in (imp.get("grounds") or {}).items():
    seen.append(c)
    err += [f"grounds {c} -> {t}: not an upstream class" for t in targets if t not in up]
for c, d in (imp.get("divergence") or {}).items():
    seen.append(c)
    if not d.get("register") or d["register"] not in reg or not d.get("why"):
        err.append(f"divergence {c}: register tag / why missing")
for k, g in (imp.get("out-of-scope") or {}).items():
    if not str(g.get("reason", "")).strip():
        err.append(f"out-of-scope {k}: no reason")
    seen += g.get("concepts", [])
dup = {c for c in seen if seen.count(c) > 1}
err += [f"{c}: classified more than once" for c in sorted(dup)]
err += [f"{c}: not classified" for c in sorted(concepts - set(seen))]
err += [f"{c}: classified but has no L1 card" for c in sorted(set(seen) - concepts)]
stamp = (ROOT / "build" / "upstream-names.txt").stat().st_mtime
for d in ("foundation/okf/aicor", "verticals/robot-scientist/okf/L2-conceptual-framework/ontology",
          "foundation/okf/vrb/L2-conceptual-framework/ontology",
          "foundation/okf/normative-admissibility/L2-conceptual-framework/ontology"):
    base = Path.home() / "ResearchSpace" / d
    newer = [p for p in base.rglob("*") if p.is_file() and p.stat().st_mtime > stamp] if base.exists() else []
    if newer:
        err.append(f"upstream {d} changed after this module's upstream snapshot ({len(newer)} files): re-run make upstream")
if err:
    print("\n".join(err[:40]))
    print(f"imports: FAIL — {len(err)} problems")
    sys.exit(1)
g = imp.get("grounds") or {}
print(f"imports: PASS — {len(g)} concepts grounded in {len({t for v in g.values() for t in v})} upstream classes, "
      f"{len(imp.get('divergence') or {})} divergences (registered), "
      f"{sum(len(v['concepts']) for v in (imp.get('out-of-scope') or {}).values())} out of scope; upstream unchanged")
