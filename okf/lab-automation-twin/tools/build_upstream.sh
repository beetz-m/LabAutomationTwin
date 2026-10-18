#!/usr/bin/env bash
# Compile the frozen upstream union (AICOR + robot-scientist + VRB + normative-admissibility) with AICOR's own
# exporter, read-only, into build/upstream-aicor-ontology.{ttl,owl}, and list its names (build/upstream-names.txt).
set -euo pipefail
cd "$(dirname "$0")/.."
RS_HOME=${RESEARCHSPACE:-$HOME/ResearchSpace}
PY=${PY:-../../env_cad/bin/python}
P=build/upstream_probe
rm -rf "$P"; mkdir -p "$P/L2-conceptual-framework/ontology"
ln -sfn "$RS_HOME/foundation/okf/aicor" build/aicor
printf -- '---\ntype: dl-definition\ntitle: probe\n---\n# probe\n\n## Manchester syntax\n\n```\nClass: LabTwinUpstreamProbe\n    SubClassOf: dul:PhysicalObject\n```\n' > "$P/L2-conceptual-framework/ontology/probe-dl.md"
"$PY" "$RS_HOME/tools/okf_reason.py" "$P" --onto L2-conceptual-framework/ontology \
    --onto "$RS_HOME/verticals/robot-scientist/okf/L2-conceptual-framework/ontology" \
    --onto "$RS_HOME/foundation/okf/vrb/L2-conceptual-framework/ontology" \
    --onto "$RS_HOME/foundation/okf/normative-admissibility/L2-conceptual-framework/ontology" --prefix upstream >/dev/null
cp "$P/L2-conceptual-framework/out/upstream-aicor-ontology.ttl" "$P/L2-conceptual-framework/out/upstream-aicor-ontology.owl" build/
cp "$P/L2-conceptual-framework/out/reasoner-report.md" build/upstream-reasoner-report.md
{ grep -oE '^:[A-Za-z_][A-Za-z0-9_]* a owl:(Class|ObjectProperty|DatatypeProperty|NamedIndividual)' build/upstream-aicor-ontology.ttl
  grep -oE '^:[A-Za-z_][A-Za-z0-9_]* a :[A-Za-z]' build/upstream-aicor-ontology.ttl; } \
  | sed -E 's/^:([^ ]+) .*/\1/' | grep -v '^LabTwinUpstreamProbe$' | sort -u > build/upstream-names.txt
echo "upstream: $(wc -l < build/upstream-names.txt) names; $(grep -m1 'global consistency' build/upstream-reasoner-report.md)"
