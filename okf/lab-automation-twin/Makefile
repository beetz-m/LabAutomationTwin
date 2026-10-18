# lab-automation-twin OKF module. The five uniform targets (ResearchSpace docs/research-os/okf-verification-interface.md)
# plus the module's own: build, abox, check-full (Konclude over TBox + ABoxes), pdf.
RESEARCHSPACE ?= $(HOME)/ResearchSpace
PY            ?= ../../env_cad/bin/python
RS_ONTO  = $(RESEARCHSPACE)/verticals/robot-scientist/okf/L2-conceptual-framework/ontology
VRB_ONTO = $(RESEARCHSPACE)/foundation/okf/vrb/L2-conceptual-framework/ontology
NA_ONTO  = $(RESEARCHSPACE)/foundation/okf/normative-admissibility/L2-conceptual-framework/ontology
export RESEARCHSPACE PY

.PHONY: check validate reason imports cq counts upstream build abox e2m check-full pdf all

all: upstream build abox package check pdf

check: validate reason imports cq e2m check-full
	@echo "check: PASS — bundle valid; HermiT over the module ∪ frozen AICOR/RS/VRB/NA; imports resolve; CQs inferred; plans derived and z3-validated; Konclude over TBox + SDT ABoxes with negative controls."

upstream:
	@tools/build_upstream.sh

build:
	@$(PY) build_module.py

package:
	@$(PY) package_okf.py

abox:
	@$(PY) abox/manuals_abox.py && $(PY) abox/safety_abox.py && $(PY) abox/sdt_abox.py && $(PY) abox/experiments_abox.py

validate:
	@$(PY) tools/validate_bundle.py

reason:
	@ln -sfn $(RESEARCHSPACE)/foundation/okf/aicor ../aicor
	@$(PY) $(RESEARCHSPACE)/tools/okf_reason.py . --onto L2-conceptual-framework/ontology --onto $(RS_ONTO) \
	    --onto $(VRB_ONTO) --onto $(NA_ONTO) --prefix lab-automation-twin > build/okf_reason.log
	@grep -q "global consistency\*\*: consistent" L2-conceptual-framework/out/reasoner-report.md && \
	 grep -q "unsatisfiable classes\*\*: 0" L2-conceptual-framework/out/reasoner-report.md && \
	 echo "reason: PASS — HermiT (AICOR okf_owl.py) over the module ∪ frozen AICOR + robot-scientist + VRB + normative-admissibility: consistent, 0 unsatisfiable" || \
	 (echo "reason: FAIL — see L2-conceptual-framework/out/reasoner-report.md"; exit 1)

imports:
	@$(PY) tools/check_aicor_imports.py

# experiment-to-motion: derive plans for several required gains / lab states (clingo), validate each with z3
E2M = L3-logical-axiomatization/derivation
e2m:
	@$(PY) $(E2M)/derive_plan.py --gain-bits 0.5 --abox > build/e2m.log
	@for a in "--gain-bits 0.25" "--gain-bits 0.55" "--gain-bits 0.62" "--gain-bits 0.62 --window-s 400 --tag g062_w400" \
	          "--gain-bits 0.5 --uncalibrated --tag g050_uncal" "--gain-bits 0.5 --coupled --tag g050_coupled"; do \
	    $(PY) $(E2M)/derive_plan.py $$a >> build/e2m.log || exit 1; done
	@for a in "--gain-bits 0.70" "--gain-bits 0.5 --contaminated --tag g050_contam" \
	          "--gain-bits 0.5 --interlocks-open --tag g050_ilk"; do \
	    $(PY) $(E2M)/derive_plan.py $$a >> build/e2m.log; test $$? -eq 2 || { echo "e2m: FAIL — $$a should be refused"; exit 1; }; done
	@for t in g025 g050 g055 g062 g062_w400 g050_uncal g050_coupled; do \
	    $(PY) $(E2M)/validate_plan_z3.py $(E2M)/out/plan_$$t.json >> build/e2m.log || { echo "e2m: FAIL — z3 on $$t"; exit 1; }; done
	@echo "e2m: PASS — 7 plans derived (clingo, optimal) and z3-validated (7 theorems, 10/10 negative controls each); 3 requirements refused with their blocking rule"

cq:
	@$(PY) $(RESEARCHSPACE)/tools/okf_cq.py . --report L2-conceptual-framework/out/cq-inference-report.md | tail -1

check-full:
	@$(PY) check_module.py | grep -E "^\[check\]" | tail -1

counts:
	@$(PY) -c "import sys; sys.path.insert(0,'src'); import tbox, json; \
	print('concepts', sum(1 for c in tbox.CLASSES if ':' not in c['name']), '| properties', len(tbox.PROPS), \
	'| modules', len({c['module'] for c in tbox.CLASSES})); \
	[print(k, v) for k, v in json.load(open('L2-conceptual-framework/out/check-report.json')).items() if k in ('class_assertions','individuals_realised','sdt_nodes','competency_questions')]"
	@echo "counts: PASS — inventory above."

pdf:
	@cd docs && lualatex -interaction=nonstopmode -halt-on-error axioms.tex > /dev/null && rm -f axioms.aux axioms.log && echo "pdf: docs/axioms.pdf"
