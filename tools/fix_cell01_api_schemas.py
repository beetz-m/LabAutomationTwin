"""Fix two authoring bugs in the Cell 01 BioPhysical v2 USD (minimal textual edit, everything else untouched).

1. API schemas were authored as a plain attribute inside the prim body,
       def Cube "Floor" { ... uniform token[] apiSchemas = ["PhysicsCollisionAPI"] }
   which USD/PhysX ignore (0 colliders at runtime). They must be prim metadata:
       def Cube "Floor" (
           prepend apiSchemas = ["PhysicsCollisionAPI"]
       ) { ... }
2. The layer has no time-code range, so Isaac Sim loops a single frame and time-accumulating sensors
   and controllers produce no output. Adds startTimeCode / endTimeCode / timeCodesPerSecond.

Usage: env_cad/bin/python tools/fix_cell01_api_schemas.py <scene.usda> [--check]
"""

import re
import sys

ATTR = re.compile(r'^(?P<ind>\s*)uniform token\[\] apiSchemas = (?P<val>\[.*\])\s*$')
DEF = re.compile(r'^(?P<ind>\s*)def (?P<type>\w+ )?"(?P<name>[^"]+)"\s*$')


def fix(lines):
    out = list(lines)
    fixed = []
    for i in range(len(out) - 1, -1, -1):  # bottom-up so earlier indices stay valid
        m = ATTR.match(out[i])
        if not m:
            continue
        ind = m.group("ind")
        parent_ind = ind[:-4] if len(ind) >= 4 else ""
        j = i - 1
        while j >= 0 and not (DEF.match(out[j]) and DEF.match(out[j]).group("ind") == parent_ind):
            j -= 1
        if j < 0 or out[j + 1].strip() != "{":
            raise SystemExit(f"line {i + 1}: could not find the owning 'def' line followed by '{{'")
        d = DEF.match(out[j])
        del out[i]
        out[j:j + 1] = [f'{parent_ind}def {d.group("type") or ""}"{d.group("name")}" (\n',
                         f'{parent_ind}    prepend apiSchemas = {m.group("val")}\n',
                         f'{parent_ind})\n']
        fixed.append(d.group("name"))
    return out, fixed[::-1]


def add_timecodes(lines):
    if any("endTimeCode" in l for l in lines[:15]):
        return lines, False
    k = next(i for i, l in enumerate(lines) if l.strip().startswith("defaultPrim"))
    ind = re.match(r"\s*", lines[k]).group(0)
    return lines[:k + 1] + [f"{ind}startTimeCode = 0\n", f"{ind}endTimeCode = 1000000\n",
                            f"{ind}timeCodesPerSecond = 60\n"] + lines[k + 1:], True


def main():
    path = sys.argv[1]
    lines = open(path).readlines()
    new, fixed = fix(lines)
    new, tc = add_timecodes(new)
    print(f"API-schema attributes moved to metadata: {len(fixed)} {fixed}; time codes added: {tc}")
    if "--check" in sys.argv:
        sys.exit(1 if fixed or tc else 0)
    open(path, "w").writelines(new)


if __name__ == "__main__":
    main()
