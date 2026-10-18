"""The experiments axiomatized as biomedical experiments, in OWL 2 DL, checked by a reasoner.

One source (the axioms below, written in a small DL syntax) gives three renderings: DL notation (LaTeX and text),
OWL functional syntax, and an owlready2 ontology that HermiT reasons over. Compared with the first axiomatization
(rsa/experiment_dl.py, generated from the LDL concept patterns):

  * BFO-style upper level: material entities, qualities, roles and dispositions, processes (planned and biological),
    information content entities (plans, data, hypotheses); parthood never crosses these kinds.
  * the design is a plan (study design with arms, administration specifications and comparisons) that the experiment
    executes; cultures are experimental units assigned to arms (membership, not parthood); agents are chemical
    entities bearing roles (challenge, rescue, vehicle) and dispositions (toxicity).
  * arms, comparisons, designs and experiments are DEFINED concepts: the reasoner classifies them from their content
    (an arm with a challenge and no rescue is a challenge-only arm; a comparison of a challenge-only arm with a negative
    control is an injury-validity comparison; ...). Closure axioms in the ABox make the negations decidable.
  * the biomedical adequacy of a design (replicates, vehicle control, agent-alone control) is part of the concept
    hierarchy, so the current challenge-rescue experiment and an improved design are classified differently.
  * hypotheses are information entities that posit processes (a loss of recovery capacity); nothing biological is
    asserted as fact (D016). Size is measured as a proxy for viability (isProxyFor), not as viability.
  * aligned to Cell 01's biology ontology (read only), and checked for joint consistency with it.

What OWL 2 DL cannot state (single difference, off-edge placement, time order across paths, the number of replicates
under the closed world) is checked by closed-world queries over the reasoned ABox.

    env_cad/bin/python -m rsa.experiment_ontology      # rsa/out/experiment_ontology/*
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import sys
import time
import types as pytypes

import owlready2 as o

from .experiment_concepts import derived_and_placed, ex_key, exposures, role_of
from .ldl import LAB, OUT, dslots, fmt, parse, slot

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DST = os.path.join(OUT, "experiment_ontology")
XP = "https://aicor.example/okf/experiment#"
BIO = "https://aicor.example/okf/biology#"
BIO_TTL = os.path.expanduser("~/ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff/biology/ontology/"
                             "aicor-biology.ttl")
PLAN = os.path.join(ROOT, "okf", "lab-automation-twin", "L3-logical-axiomatization", "derivation", "out", "plan_g050.json")
MIN_REPLICATES = 3      # ILLUSTRATIVE design criterion (common practice), not a biomedical parameter


# ================================================================================================= DL syntax
class E:
    def __and__(self, x):
        return And(self, x)

    def __or__(self, x):
        return Or(self, x)

    def __invert__(self):
        return Not(self)


class A(E):
    def __init__(self, n):
        self.n = n

    def dl(self, m):
        if self.n in ("⊤", "⊥"):
            return self.n
        if self.n.startswith("bio:"):
            return self.n if m == "txt" else rf"\mathsf{{bio{{:}}{self.n[4:]}}}"
        return self.n if m == "txt" else rf"\mathsf{{{self.n}}}"

    def ofn(self):
        return {"⊤": "owl:Thing", "⊥": "owl:Nothing"}.get(self.n, self.n if self.n.startswith("bio:") else "xp:" + self.n)

    def owl(self, K):
        return {"⊤": o.Thing, "⊥": o.Nothing}.get(self.n) or K.cls(self.n)

    def names(self):
        return {self.n} - {"⊤", "⊥"}


class Nary(E):
    op, sym, ofn_name = "", "", ""

    def __init__(self, *xs):
        self.xs = [x if isinstance(x, E) else A(x) for x in xs]

    def dl(self, m):
        return "(" + f" {self.sym} ".join(x.dl(m) for x in self.xs) + ")"

    def ofn(self):
        return f"{self.ofn_name}(" + " ".join(x.ofn() for x in self.xs) + ")"

    def names(self):
        return set().union(*(x.names() for x in self.xs))


class And(Nary):
    sym, ofn_name = "⊓", "ObjectIntersectionOf"

    def owl(self, K):
        return o.And([x.owl(K) for x in self.xs])


class Or(Nary):
    sym, ofn_name = "⊔", "ObjectUnionOf"

    def owl(self, K):
        return o.Or([x.owl(K) for x in self.xs])


class Not(E):
    def __init__(self, x):
        self.x = x if isinstance(x, E) else A(x)

    def dl(self, m):
        return "¬" + self.x.dl(m)

    def ofn(self):
        return f"ObjectComplementOf({self.x.ofn()})"

    def owl(self, K):
        return o.Not(self.x.owl(K))

    def names(self):
        return self.x.names()


class Inv:
    def __init__(self, r):
        self.r = r

    def dl(self, m):
        return (self.r + "⁻") if m == "txt" else rf"\mathit{{{self.r}}}^{{-}}"

    def ofn(self):
        return f"ObjectInverseOf(xp:{self.r})"

    def owl(self, K):
        return o.Inverse(K.prop(self.r))


def rdl(r, m):
    return r.dl(m) if isinstance(r, Inv) else (r if m == "txt" else rf"\mathit{{{r}}}")


def rofn(r):
    return r.ofn() if isinstance(r, Inv) else "xp:" + r


def rowl(r, K):
    return r.owl(K) if isinstance(r, Inv) else K.prop(r)


class Some(E):
    def __init__(self, r, c="⊤"):
        self.r, self.c = r, c if isinstance(c, E) else A(c)

    def dl(self, m):
        return f"∃{rdl(self.r, m)}.{self.c.dl(m)}"

    def ofn(self):
        return f"ObjectSomeValuesFrom({rofn(self.r)} {self.c.ofn()})"

    def owl(self, K):
        return rowl(self.r, K).some(self.c.owl(K))

    def names(self):
        return self.c.names()


class All(Some):
    def dl(self, m):
        return f"∀{rdl(self.r, m)}.{self.c.dl(m)}"

    def ofn(self):
        return f"ObjectAllValuesFrom({rofn(self.r)} {self.c.ofn()})"

    def owl(self, K):
        return rowl(self.r, K).only(self.c.owl(K))


class Card(E):
    def __init__(self, op, n, r, c="⊤"):
        self.op, self.n, self.r, self.c = op, n, r, c if isinstance(c, E) else A(c)

    def dl(self, m):
        return f"({ {'min': '≥', 'max': '≤', 'exact': '='}[self.op]}{self.n} {rdl(self.r, m)}.{self.c.dl(m)})"

    def ofn(self):
        name = {"min": "ObjectMinCardinality", "max": "ObjectMaxCardinality", "exact": "ObjectExactCardinality"}[self.op]
        return f"{name}({self.n} {rofn(self.r)} {self.c.ofn()})"

    def owl(self, K):
        p = rowl(self.r, K)
        return {"min": p.min, "max": p.max, "exact": p.exactly}[self.op](self.n, self.c.owl(K))

    def names(self):
        return self.c.names()


def Min(n, r, c="⊤"):
    return Card("min", n, r, c)


def Max(n, r, c="⊤"):
    return Card("max", n, r, c)


def Exactly(n, r, c="⊤"):
    return Card("exact", n, r, c)


class DSome(E):
    """∃dp.decimal, optionally with a lower bound (a datatype restriction)."""

    def __init__(self, dp, lo=None):
        self.dp, self.lo = dp, lo

    def dl(self, m):
        dt = "decimal" if m == "txt" else r"\mathsf{decimal}"
        b = "" if self.lo is None else (f"[≥{self.lo}]" if m == "txt" else rf"_{{\geq {self.lo}}}")
        return f"∃{rdl(self.dp, m)}.{dt}{b}"

    def ofn(self):
        if self.lo is None:
            return f"DataSomeValuesFrom(xp:{self.dp} xsd:decimal)"
        return f'DataSomeValuesFrom(xp:{self.dp} DatatypeRestriction(xsd:decimal xsd:minInclusive "{self.lo}"^^xsd:decimal))'

    def owl(self, K):
        p = K.dprop(self.dp)
        return p.some(float if self.lo is None else o.ConstrainedDatatype(float, min_inclusive=self.lo))

    def names(self):
        return set()


def C(x):
    return x if isinstance(x, E) else A(x)


# ---------------------------------------------------------------------------------------------- axioms
class Ax:
    note = ""


class Sub(Ax):
    def __init__(self, l, r, note=""):
        self.l, self.r, self.note = C(l), C(r), note

    def dl(self, m):
        return f"{self.l.dl(m)} ⊑ {strip(self.r.dl(m))}"

    def ofn(self):
        return f"SubClassOf({self.l.ofn()} {self.r.ofn()})"


class Eq(Sub):
    def dl(self, m):
        return f"{self.l.dl(m)} ≡ {strip(self.r.dl(m))}"

    def ofn(self):
        return f"EquivalentClasses({self.l.ofn()} {self.r.ofn()})"


class Disj(Ax):
    def __init__(self, *cs, note=""):
        self.cs, self.note = [C(c) for c in cs], note

    def dl(self, m):
        if len(self.cs) == 2:
            return f"{self.cs[0].dl(m)} ⊓ {self.cs[1].dl(m)} ⊑ ⊥"
        return ("Disjoint(" if m == "txt" else r"\mathrm{Disjoint}(") + (", " if m == "txt" else r",\allowbreak ").join(
            c.dl(m) for c in self.cs) + ")"

    def ofn(self):
        return "DisjointClasses(" + " ".join(c.ofn() for c in self.cs) + ")"


class SubR(Ax):
    def __init__(self, r, s, note=""):
        self.r, self.s, self.note = r, s, note

    def dl(self, m):
        return f"{rdl(self.r, m)} ⊑ {rdl(self.s, m)}"

    def ofn(self):
        return f"SubObjectPropertyOf({rofn(self.r)} {rofn(self.s)})"


class Trans(Ax):
    def __init__(self, r, note=""):
        self.r, self.note = r, note

    def dl(self, m):
        return ("Trans(" if m == "txt" else r"\mathrm{Trans}(") + rdl(self.r, m) + ")"

    def ofn(self):
        return f"TransitiveObjectProperty(xp:{self.r})"


class Func(Trans):
    def dl(self, m):
        return ("Func(" if m == "txt" else r"\mathrm{Func}(") + rdl(self.r, m) + ")"

    def ofn(self):
        return f"FunctionalObjectProperty(xp:{self.r})"


class FuncD(Trans):
    def dl(self, m):
        return ("Func(" if m == "txt" else r"\mathrm{Func}(") + rdl(self.r, m) + ")"

    def ofn(self):
        return f"FunctionalDataProperty(xp:{self.r})"


class InvR(Ax):
    def __init__(self, r, s, note=""):
        self.r, self.s, self.note = r, s, note

    def dl(self, m):
        return f"{rdl(self.r, m)} ≡ {Inv(self.s).dl(m)}"

    def ofn(self):
        return f"InverseObjectProperties(xp:{self.r} xp:{self.s})"


class Chain(Ax):
    def __init__(self, rs, s, note=""):
        self.rs, self.s, self.note = rs, s, note

    def dl(self, m):
        return " ∘ ".join(rdl(r, m) for r in self.rs) + f" ⊑ {rdl(self.s, m)}"

    def ofn(self):
        return f"SubObjectPropertyOf(ObjectPropertyChain({' '.join(rofn(r) for r in self.rs)}) xp:{self.s})"


def strip(s):
    """Drop the outer parentheses of a top-level conjunction on the right-hand side."""
    if s.startswith("(") and s.endswith(")"):
        d = 0
        for i, ch in enumerate(s):
            d += ch == "("
            d -= ch == ")"
            if d == 0 and i < len(s) - 1:
                return s
        return s[1:-1]
    return s


# ================================================================================================= the TBox
OBJ_PROPS = ["hasPart", "partOf", "hasPhase", "hasStep", "hasWell", "hasOrganoid", "hasCell", "hasMedium", "hasArm",
             "hasComparisonSpec", "hasAdministrationSpec", "hasObjective", "contains", "containedIn", "locatedIn",
             "hasParticipant", "participatesIn", "hasSpecifiedInput", "hasSpecifiedOutput", "executes", "bearerOf",
             "inheresIn", "realizedIn", "isAbout", "isProxyFor", "assignedTo", "hasAssignedUnit", "compares", "licenses",
             "usesAgent", "precedes", "derivedFrom", "posits", "delays", "hasFactor", "hasLevel", "levelOf", "atLevel",
             "contrasts", "differenceOf", "hasInteractionContrast", "hasExpectedOutcome", "hasReadout", "measures",
             "hasAnalysisPlan", "hasDecisionRule", "appliesTo", "hasDevice", "providesEnvironment", "hasReadoutBinding",
             "stocks", "underEnvironment"]
DATA_PROPS = ["dose_au", "atTime_h", "fromTime_h", "toTime_h", "expectedInformationGain_bits", "radius_um",
              "predictedMean_um", "predictedSd_um", "probability", "wellRow", "wellColumn", "threshold_sd"]


def tbox():
    S = []

    def sec(title, text, axs):
        S.append(dict(title=title, text=text, axioms=axs))

    sec("Upper level", "A BFO-style upper level. Continuants (material entities, qualities, realizable entities, "
        "information content entities) and occurrents (processes) are disjoint; planned processes are distinct from "
        "biological processes.", [
            Sub("MaterialEntity", "Continuant"), Sub("SpecificallyDependentContinuant", "Continuant"),
            Sub("Quality", "SpecificallyDependentContinuant"), Sub("RealizableEntity", "SpecificallyDependentContinuant"),
            Sub("InformationContentEntity", "Continuant"), Sub("Process", "Occurrent"),
            Disj("Continuant", "Occurrent"),
            Disj("MaterialEntity", "SpecificallyDependentContinuant", "InformationContentEntity"), Disj("Quality", "RealizableEntity"),
            Sub("Role", "RealizableEntity"), Sub("Disposition", "RealizableEntity"), Disj("Role", "Disposition"),
            Sub("PlannedProcess", "Process"), Sub("BiologicalProcess", "Process"), Disj("PlannedProcess", "BiologicalProcess"),
            Sub("PlanSpecification", "InformationContentEntity"), Sub("DataItem", "InformationContentEntity"),
            Sub("Hypothesis", "InformationContentEntity"), Sub("Objective", "InformationContentEntity"),
            Sub("Conclusion", "InformationContentEntity"),
            Disj("PlanSpecification", "DataItem", "Hypothesis", "Objective", "Conclusion")])

    sec("Relations and partonomy", "Parthood is transitive and kind-preserving: processes have processes as parts, "
        "material entities material entities, information entities information entities. Its kinds are simple "
        "sub-roles (so they may be counted). Location, membership, participation, execution and bearing are not "
        "parthood.", [
            Trans("hasPart"), InvR("partOf", "hasPart"),
            *[SubR(r, "hasPart") for r in ("hasPhase", "hasStep", "hasWell", "hasOrganoid", "hasCell", "hasMedium",
                                           "hasArm", "hasComparisonSpec", "hasAdministrationSpec", "hasObjective")],
            Sub("Process", All("hasPart", "Process")), Sub("MaterialEntity", All("hasPart", "MaterialEntity")),
            Sub("InformationContentEntity", All("hasPart", "InformationContentEntity")),
            InvR("containedIn", "contains"), Chain(["containedIn", "partOf"], "locatedIn"),
            InvR("participatesIn", "hasParticipant"), Chain(["hasPart", "hasParticipant"], "hasParticipant"),
            SubR("hasSpecifiedInput", "hasParticipant"),
            InvR("inheresIn", "bearerOf"), Func("inheresIn"),
            InvR("hasAssignedUnit", "assignedTo"), Func("assignedTo"), Func("usesAgent"), Trans("precedes"),
            Sub(Some("executes"), "PlannedProcess"), Sub("⊤", All("executes", "PlanSpecification")),
            Sub(Some("isAbout"), "InformationContentEntity"), Sub(Some("bearerOf"), "Continuant"),
            Sub("⊤", All("bearerOf", "SpecificallyDependentContinuant")), Sub(Some("realizedIn"), "RealizableEntity"),
            Sub("⊤", All("realizedIn", "Process")),
            *[FuncD(d) for d in ("dose_au", "atTime_h", "fromTime_h", "toTime_h", "expectedInformationGain_bits",
                                 "radius_um", "wellRow", "wellColumn")]])

    sec("Biological material and labware", "An organoid culture is organoids in medium; an organoid has cells. A well "
        "holds at most one culture; a culture is in a well, not part of it. Chemical agents bear roles in the "
        "experiment (challenge, rescue, vehicle) and dispositions (toxicity); size is a quality of organoids, viability "
        "and recovery capacity are dispositions of cultures.", [
            Sub("OrganoidCulture", And("MaterialEntity", Some("hasOrganoid", "Organoid"), Some("hasMedium", "CultureMedium"))),
            Sub("Organoid", And("MaterialEntity", Some("hasCell", "Cell"))),
            Sub("Cell", "MaterialEntity"), Sub("CultureMedium", "MaterialEntity"), Sub("ChemicalAgent", "MaterialEntity"),
            Sub("Plate", And("MaterialEntity", Some("hasWell", "Well"))),
            Sub("Well", And("MaterialEntity", Max(1, "contains", "OrganoidCulture"))),
            Disj("OrganoidCulture", "Organoid", "Cell", "CultureMedium", "ChemicalAgent", "Plate", "Well"),
            Sub("OrganoidSize", And("Quality", Some("inheresIn", "Organoid"))),
            Sub("Viability", And("Disposition", Some("inheresIn", "OrganoidCulture"), All("realizedIn", "CultureGrowth"))),
            Sub("RecoveryCapacity", And("Disposition", Some("inheresIn", "OrganoidCulture"), All("realizedIn", "RecoveryProcess"))),
            Sub("ToxicityDisposition", And("Disposition", Some("inheresIn", "ChemicalAgent"), All("realizedIn", "InjuryProcess"))),
            Eq("Toxicant", And("ChemicalAgent", Some("bearerOf", "ToxicityDisposition"))),
            *[Sub(r, "Role") for r in ("ChallengeAgentRole", "RescueAgentRole", "VehicleRole", "ExperimentalUnitRole")],
            Disj("ChallengeAgentRole", "RescueAgentRole", "VehicleRole", "ExperimentalUnitRole"),
            Eq("ChallengeAgent", And("ChemicalAgent", Some("bearerOf", "ChallengeAgentRole"))),
            Eq("RescueAgent", And("ChemicalAgent", Some("bearerOf", "RescueAgentRole"))),
            Eq("Vehicle", And("ChemicalAgent", Some("bearerOf", "VehicleRole"))),
            Disj("ChallengeAgent", "RescueAgent", "Vehicle"),
            Sub("ChallengeAgent", "Toxicant", note="the challenge role is given to an agent because of its toxicity"),
            Eq("ExperimentalUnit", And("OrganoidCulture", Some("bearerOf", "ExperimentalUnitRole")))])

    sec("Biological processes", "Processes in which the cultures participate. A loss of recovery capacity (a point of "
        "no return) is a process type that hypotheses may posit; nothing here asserts that it occurs.", [
            *[Sub(p, And("BiologicalProcess", Some("hasParticipant", "OrganoidCulture")))
              for p in ("InjuryProcess", "ProtectiveResponse", "RecoveryProcess", "CellDeath", "CultureGrowth",
                        "LossOfRecoveryCapacity")],
            Disj("InjuryProcess", "ProtectiveResponse", "RecoveryProcess", "CellDeath", "CultureGrowth")])

    sec("Plans: designs, arms, administrations, comparisons",
        "A study design has arms and comparisons; an arm specifies the administrations its units receive (agent, dose, "
        "time). Arm types are defined by what is administered, comparison types by the arms compared, design types by "
        "their arms and comparisons; the reasoner classifies them. Replication and the information target are "
        "ILLUSTRATIVE design criteria.", [
            Sub("StudyDesign", And("PlanSpecification", Some("hasObjective", "Objective"), Some("hasArm", "ArmSpecification"))),
            Sub("ArmSpecification", And("PlanSpecification", All("hasAdministrationSpec", "AdministrationSpecification"))),
            Sub("AdministrationSpecification", And("PlanSpecification", Exactly(1, "usesAgent", "ChemicalAgent"),
                                                   DSome("dose_au"), DSome("atTime_h"))),
            Sub("ComparisonSpecification", And("PlanSpecification", Exactly(2, "compares", "ArmSpecification"))),
            Disj("StudyDesign", "ArmSpecification", "AdministrationSpecification", "ComparisonSpecification"),
            Eq("ChallengeSpec", And("AdministrationSpecification", Some("usesAgent", "ChallengeAgent"))),
            Eq("RescueSpec", And("AdministrationSpecification", Some("usesAgent", "RescueAgent"))),
            Eq("VehicleSpec", And("AdministrationSpecification", Some("usesAgent", "Vehicle"))),
            Eq("UntreatedArm", And("ArmSpecification", Not(Some("hasAdministrationSpec", "AdministrationSpecification")))),
            Eq("VehicleControlArm", And("ArmSpecification", Some("hasAdministrationSpec", "VehicleSpec"),
                                        Not(Some("hasAdministrationSpec", Or("ChallengeSpec", "RescueSpec"))))),
            Eq("NegativeControlArm", Or("UntreatedArm", "VehicleControlArm")),
            Eq("ChallengeOnlyArm", And("ArmSpecification", Some("hasAdministrationSpec", "ChallengeSpec"),
                                       Not(Some("hasAdministrationSpec", "RescueSpec")))),
            Eq("RescueOnlyArm", And("ArmSpecification", Some("hasAdministrationSpec", "RescueSpec"),
                                    Not(Some("hasAdministrationSpec", "ChallengeSpec")))),
            Eq("ChallengeRescueArm", And("ArmSpecification", Some("hasAdministrationSpec", "ChallengeSpec"),
                                         Some("hasAdministrationSpec", "RescueSpec"))),
            Eq("ReplicatedArm", And("ArmSpecification", Min(MIN_REPLICATES, "hasAssignedUnit", "ExperimentalUnit"))),
            Eq("InjuryValidityComparison", And("ComparisonSpecification", Some("compares", "ChallengeOnlyArm"),
                                               Some("compares", "NegativeControlArm"))),
            Eq("RescueEffectComparison", And("ComparisonSpecification", Some("compares", "ChallengeRescueArm"),
                                             Some("compares", "ChallengeOnlyArm"))),
            Eq("AgentAloneComparison", And("ComparisonSpecification", Some("compares", "RescueOnlyArm"),
                                           Some("compares", "NegativeControlArm"))),
            Eq("RescueTimingComparison", And("ComparisonSpecification", Exactly(2, "compares", "ChallengeRescueArm"))),
            Eq("DiscriminationObjective", And("Objective", Min(2, "isAbout", "Hypothesis")))])

    sec("Factors, levels and treatments", "A factor is what the experimenter varies (here: the challenge, the time of "
        "the rescue); its levels are the values it takes, each specifying administrations. An arm's treatment is one "
        "level of every factor (atLevel; a level is shared by arms, so this is not parthood). A comparison contrasts "
        "the factors in which its two arms differ; a well-formed comparison contrasts exactly one. Which factors a "
        "comparison contrasts, and whether an arm's schedule is the union of its levels, are computed under the closed "
        "world and asserted.", [
            Sub("Factor", And("PlanSpecification", Min(2, "hasLevel", "FactorLevel"))),
            Sub("FactorLevel", And("PlanSpecification", Exactly(1, "levelOf", "Factor"))),
            InvR("levelOf", "hasLevel"), SubR("hasLevel", "hasPart"), SubR("hasFactor", "hasPart"),
            Sub("ArmSpecification", All("atLevel", "FactorLevel")),
            Sub("ComparisonSpecification", All("contrasts", "Factor")),
            Eq("SingleFactorComparison", And("ComparisonSpecification", Exactly(1, "contrasts", "Factor"))),
            Eq("FactorialDesign", And("StudyDesign", Min(2, "hasFactor", "Factor"))),
            Eq("WellContrastedDesign", And("StudyDesign", All("hasComparisonSpec", "SingleFactorComparison"))),
            Sub("InteractionContrast", And("PlanSpecification", Exactly(2, "differenceOf", "ComparisonSpecification"))),
            SubR("hasInteractionContrast", "hasPart"),
            Eq("InteractionAwareDesign", And("StudyDesign", Some("hasInteractionContrast", "InteractionContrast"))),
            Disj("Factor", "FactorLevel", "StudyDesign", "ArmSpecification", "AdministrationSpecification",
                 "ComparisonSpecification", "InteractionContrast")])

    sec("Controls", "A control is defined by what it controls for. Negative controls (untreated, vehicle) give the "
        "baseline; the agent-alone arm separates the rescue agent's own effect from rescue of injury; a positive "
        "control is an arm whose outcome is expected from prior evidence, so that a null result elsewhere can be "
        "interpreted (the agent and the assay worked in this run).", [
            Sub("Expectation", "DataItem"), Sub("PriorEvidence", "DataItem"),
            Eq("EvidenceBasedExpectation", And("Expectation", Some("derivedFrom", "PriorEvidence"))),
            Eq("PositiveControlArm", And("ArmSpecification", Some("hasExpectedOutcome", "EvidenceBasedExpectation"))),
            Eq("PositiveControlComparison", And("ComparisonSpecification", Some("compares", "PositiveControlArm"),
                                                Some("compares", "ChallengeOnlyArm"))),
            Eq("PositiveControlledDesign", And("StudyDesign", Some("hasComparisonSpec", "PositiveControlComparison")))])

    sec("Readouts and analysis plan", "A readout (endpoint) specifies what is measured, when and by which assay, and "
        "what it is a proxy for. The analysis plan, part of the design and fixed before the run, has one decision rule "
        "per comparison (a threshold test, a Bayesian update over the hypotheses, or an estimate) and a rule for "
        "deviations. A design is pre-specified when every comparison is covered by a rule.", [
            SubR("hasReadout", "hasPart"), SubR("hasAnalysisPlan", "hasPart"), SubR("hasDecisionRule", "hasPart"),
            Sub("ReadoutSpecification", And("PlanSpecification", Some("measures", "Quality"), DSome("atTime_h"))),
            Eq("SizeReadout", And("ReadoutSpecification", Some("measures", "OrganoidSize"), Some("isProxyFor", "Viability"))),
            Sub("AnalysisPlan", And("PlanSpecification", Some("hasDecisionRule", "DecisionRule"))),
            Sub("DecisionRule", "PlanSpecification"),
            Sub("ComparisonRule", And("DecisionRule", Exactly(1, "appliesTo", "ComparisonSpecification"))),
            Sub("ThresholdRule", "ComparisonRule"), Sub("EstimationRule", "ComparisonRule"),
            Sub("BayesianUpdateRule", And("ComparisonRule", Min(2, "isAbout", "Hypothesis"))),
            Sub("DeviationRule", And("DecisionRule", Not(Some("appliesTo")))),
            Disj("ThresholdRule", "EstimationRule", "BayesianUpdateRule", "DeviationRule"),
            Disj("ReadoutSpecification", "AnalysisPlan", "DecisionRule", "Factor", "StudyDesign", "ArmSpecification",
                 "ComparisonSpecification"),
            Eq("CoveredComparison", And("ComparisonSpecification", Some(Inv("appliesTo"), "ComparisonRule"))),
            Eq("PreSpecifiedDesign", And("StudyDesign", Some("hasReadout", "ReadoutSpecification"),
                                         Some("hasAnalysisPlan", "AnalysisPlan"), All("hasComparisonSpec", "CoveredComparison"))),
            Eq("DeviationAwareDesign", And("PreSpecifiedDesign", Some("hasAnalysisPlan", Some("hasDecisionRule", "DeviationRule"))))])

    sec("Design classes", "Design types are defined by their arms, comparisons, factors and analysis plan; the "
        "reasoner places every design under each class it satisfies. Adequate control (the reviewer's standard) "
        "requires the agent-alone and vehicle controls, a positive control, replication, single-factor comparisons "
        "and a pre-specified analysis. Replication and the information target are ILLUSTRATIVE criteria.", [
            Eq("ComparativeDesign", And("StudyDesign", Min(2, "hasArm", "ArmSpecification"),
                                        Some("hasComparisonSpec", "ComparisonSpecification"))),
            Eq("ControlledDesign", And("ComparativeDesign", Some("hasArm", "NegativeControlArm"))),
            Eq("InjuryRescueDesign", And("ControlledDesign", Some("hasArm", "ChallengeRescueArm"), Some("hasArm", "ChallengeOnlyArm"),
                                         Some("hasComparisonSpec", "RescueEffectComparison"))),
            Eq("ValidatedInjuryRescueDesign", And("InjuryRescueDesign", Some("hasComparisonSpec", "InjuryValidityComparison"))),
            Eq("AgentControlledInjuryRescueDesign", And("ValidatedInjuryRescueDesign", Some("hasArm", "RescueOnlyArm"),
                                                        Some("hasArm", "VehicleControlArm"),
                                                        Some("hasComparisonSpec", "AgentAloneComparison"))),
            Eq("TherapeuticWindowDesign", And("InjuryRescueDesign", Min(2, "hasArm", "ChallengeRescueArm"))),
            Eq("ReplicatedDesign", And("StudyDesign", All("hasArm", "ReplicatedArm"))),
            Eq("AdequatelyControlledInjuryRescueDesign", And("AgentControlledInjuryRescueDesign", "PositiveControlledDesign",
                                                             "ReplicatedDesign", "WellContrastedDesign", "PreSpecifiedDesign")),
            Eq("HypothesisDiscriminatingDesign", And("StudyDesign", Some("hasObjective", "DiscriminationObjective"))),
            Eq("SufficientlyInformativeDesign", And("StudyDesign", DSome("expectedInformationGain_bits", 0.5)))])

    sec("Experiments, phases and steps", "An experiment (investigation) is a planned process that executes exactly one "
        "study design; its classification follows its design's. Its parts are three phases, their parts the steps: "
        "administrations and incubations, assays, data transformations.", [
            Sub("Investigation", And("PlannedProcess", Exactly(1, "executes", "StudyDesign"))),
            *[Eq(e, And("Investigation", Some("executes", d))) for e, d in (
                ("ComparativeExperiment", "ComparativeDesign"), ("ControlledExperiment", "ControlledDesign"),
                ("InjuryRescueExperiment", "InjuryRescueDesign"),
                ("ValidatedInjuryRescueExperiment", "ValidatedInjuryRescueDesign"),
                ("AdequatelyControlledInjuryRescueExperiment", "AdequatelyControlledInjuryRescueDesign"),
                ("TherapeuticWindowExperiment", "TherapeuticWindowDesign"), ("FactorialExperiment", "FactorialDesign"),
                ("HypothesisDiscriminatingExperiment", "HypothesisDiscriminatingDesign"))],
            Sub("ComparativeExperiment", And(Exactly(1, "hasPhase", "CultivationPhase"), Exactly(1, "hasPhase", "ObservationPhase"),
                                             Exactly(1, "hasPhase", "AnalysisPhase"))),
            Sub("Phase", "PlannedProcess"),
            Sub("CultivationPhase", And("Phase", All("hasStep", Or("Administration", "Incubation")))),
            Sub("ObservationPhase", And("Phase", All("hasStep", "Assay"))),
            Sub("AnalysisPhase", And("Phase", All("hasStep", "DataTransformation"))),
            Disj("CultivationPhase", "ObservationPhase", "AnalysisPhase"),
            Sub("Administration", And("PlannedProcess", Exactly(1, "executes", "AdministrationSpecification"),
                                      Some("hasSpecifiedInput", "ChemicalAgent"), Some("hasSpecifiedInput", "ExperimentalUnit"))),
            Eq("ChallengeAdministration", And("Administration", Some("executes", "ChallengeSpec"))),
            Eq("RescueAdministration", And("Administration", Some("executes", "RescueSpec"))),
            Sub("Incubation", And("PlannedProcess", Some("hasParticipant", "OrganoidCulture"))),
            Sub("Assay", And("PlannedProcess", Some("hasSpecifiedInput", "ExperimentalUnit"), Some("hasSpecifiedOutput", "DataItem"))),
            Sub("ImagingAssay", And("Assay", Some("hasSpecifiedOutput", "Image"))),
            Sub("DataTransformation", "PlannedProcess"),
            Sub("ImageAnalysis", And("DataTransformation", Some("hasSpecifiedInput", "Image"), Some("hasSpecifiedOutput", "SizeDatum"))),
            Sub("StatisticalComparison", And("DataTransformation", Exactly(1, "executes", "ComparisonSpecification"),
                                             Some("executes", "ComparisonRule"), Some("hasSpecifiedOutput", "EffectEstimate"))),
            Sub("ModelUpdate", And("DataTransformation", Some("hasSpecifiedOutput", "PosteriorDistribution"))),
            Disj("Phase", "Administration", "Incubation", "Assay", "DataTransformation")])

    sec("Data, hypotheses and conclusions", "Images are about units; a size datum is about organoid size and is a proxy "
        "for viability. Recovery hypotheses are about recovery processes: the graded one posits no loss of recovery "
        "capacity, the threshold one posits it, the protective one posits a protective response that delays it. "
        "Predictions derive from hypotheses; conclusions (the insights) derive from effect estimates and posteriors.", [
            Sub("Image", And("DataItem", Some("isAbout", "ExperimentalUnit"))),
            Sub("MeasurementDatum", "DataItem"),
            Sub("SizeDatum", And("MeasurementDatum", Some("isAbout", "OrganoidSize"), Some("isProxyFor", "Viability"))),
            Sub("EffectEstimate", And("DataItem", Some("derivedFrom", "SizeDatum"))),
            Sub("PosteriorDistribution", And("DataItem", Min(2, "isAbout", "Hypothesis"))),
            Sub("Prediction", And("Expectation", Some("derivedFrom", "Hypothesis"), Some("isAbout", "ComparisonSpecification"))),
            Disj("Image", "MeasurementDatum", "EffectEstimate", "PosteriorDistribution", "Expectation", "PriorEvidence"),
            Sub("RecoveryHypothesis", And("Hypothesis", Some("isAbout", "RecoveryProcess"))),
            Sub("GradedRecoveryHypothesis", And("RecoveryHypothesis", Not(Some("posits", "LossOfRecoveryCapacity")))),
            Sub("ThresholdRecoveryHypothesis", And("RecoveryHypothesis", Some("posits", "LossOfRecoveryCapacity"))),
            Sub("ProtectiveResponseHypothesis", And("ThresholdRecoveryHypothesis",
                                                    Some("posits", And("ProtectiveResponse", Some("delays", "LossOfRecoveryCapacity"))))),
            Sub("Conclusion", Some("derivedFrom", Or("EffectEstimate", "PosteriorDistribution")))])

    sec("Laboratories, devices and capabilities", "A laboratory has devices as parts; a device bears functions, "
        "dispositions realized only in processes of one kind (a dosing function only in administrations, an imaging "
        "function only in imaging assays). A laboratory's capability classes are defined by the functions its devices "
        "bear, by the environments it provides and by its validated readout bindings, so the reasoner classifies "
        "laboratories from their devices. Reagent stocks are located in a laboratory, not parts of it.", [
            Sub("Laboratory", And("MaterialEntity", Some("hasDevice", "Device"))), SubR("hasDevice", "hasPart"),
            Sub("Device", "MaterialEntity"),
            Disj("Laboratory", "Device", "OrganoidCulture", "ChemicalAgent", "Plate", "Well"),
            Sub("DeviceFunction", And("Disposition", Some("inheresIn", "Device"))),
            Sub("DosingFunction", And("DeviceFunction", All("realizedIn", "Administration"))),
            Sub("IncubationFunction", And("DeviceFunction", All("realizedIn", "Incubation"))),
            Sub("BrightfieldImagingFunction", And("DeviceFunction", All("realizedIn", "ImagingAssay"))),
            Sub("LuminescenceReadingFunction", And("DeviceFunction", All("realizedIn", "LuminescenceAssay"))),
            Sub("AbsorbanceReadingFunction", And("DeviceFunction", All("realizedIn", "AbsorbanceAssay"))),
            *[Sub(f, "DeviceFunction") for f in ("CalibrationFunction", "QuarantineFunction", "TransportFunction",
                                                 "PlateHandlingFunction", "StorageFunction")],
            Sub("EndpointAssay", "Assay"), Sub("LuminescenceAssay", "EndpointAssay"), Sub("AbsorbanceAssay", "EndpointAssay"),
            Disj("ImagingAssay", "EndpointAssay"),
            Sub("MetabolicActivity", And("Quality", Some("inheresIn", "OrganoidCulture"))),
            Sub("EnvironmentProfile", "PlanSpecification"),
            Sub("ReadoutBinding", And("InformationContentEntity", Some("isAbout", "Quality"))),
            Sub("ValidatedReadoutBinding", "ReadoutBinding"),
            *[Eq(lab, And("Laboratory", Some("hasDevice", Some("bearerOf", fn)))) for lab, fn in (
                ("DosingLab", "DosingFunction"), ("CultivationLab", "IncubationFunction"),
                ("BrightfieldImagingLab", "BrightfieldImagingFunction"), ("LuminescenceReadoutLab", "LuminescenceReadingFunction"),
                ("AbsorbanceReadoutLab", "AbsorbanceReadingFunction"), ("QualityControlledLab", "CalibrationFunction"),
                ("ContainmentCapableLab", "QuarantineFunction"), ("ConnectedLab", "TransportFunction"))],
            Eq("MultiEnvironmentLab", And("Laboratory", Min(2, "providesEnvironment", "EnvironmentProfile"))),
            Eq("ValidatedSizeReadoutLab", And("Laboratory", Some("hasReadoutBinding",
                                                                  And("ValidatedReadoutBinding", Some("isAbout", "OrganoidSize"))))),
            Eq("ValidatedMetabolicReadoutLab", And("Laboratory", Some("hasReadoutBinding",
                                                                       And("ValidatedReadoutBinding", Some("isAbout", "MetabolicActivity"))))),
            Eq("TreatmentAndImagingModule", And("DosingLab", "CultivationLab", "BrightfieldImagingLab", "ValidatedSizeReadoutLab"))])

    sec("Design requirements", "What a design needs from a laboratory follows from its content: administrations need "
        "dosing, an imaging readout needs imaging, an endpoint readout needs the corresponding reader and comes after "
        "every non-destructive observation, an environment factor needs as many controlled environments as it has "
        "levels. Requirement classes are defined, so the reasoner classifies designs by their needs. Each requirement "
        "is met by one laboratory capability class; whether the laboratories of a site meet all of a design's "
        "requirements, with its reagents, readout bindings and timing, is a closed-world question over the individuals.", [
            Eq("RequiresDosing", And("StudyDesign", Some("hasArm", Some("hasAdministrationSpec", "AdministrationSpecification")))),
            Eq("RequiresCultivation", And("StudyDesign", Some("hasArm", "ArmSpecification"))),
            Sub("ImagingReadout", "ReadoutSpecification"), Sub("EndpointReadout", "ReadoutSpecification"),
            Sub("LuminescenceReadout", "EndpointReadout"), Sub("AbsorbanceReadout", "EndpointReadout"),
            Disj("ImagingReadout", "EndpointReadout"),
            Eq("RequiresImaging", And("StudyDesign", Some("hasReadout", "ImagingReadout"))),
            Eq("RequiresLuminescence", And("StudyDesign", Some("hasReadout", "LuminescenceReadout"))),
            Eq("RequiresAbsorbance", And("StudyDesign", Some("hasReadout", "AbsorbanceReadout"))),
            Eq("RequiresEndpointHandling", And("StudyDesign", Some("hasReadout", "EndpointReadout"))),
            Sub("EnvironmentFactor", "Factor"),
            Eq("RequiresMultipleEnvironments", And("StudyDesign", Some("hasFactor", "EnvironmentFactor")))])
    return S


#: requirement class of a design -> the laboratory capability class that meets it
REQUIREMENT_MET_BY = {"RequiresDosing": "DosingLab", "RequiresCultivation": "CultivationLab",
                      "RequiresImaging": "BrightfieldImagingLab", "RequiresLuminescence": "LuminescenceReadoutLab",
                      "RequiresAbsorbance": "AbsorbanceReadoutLab", "RequiresMultipleEnvironments": "MultiEnvironmentLab"}


ALIGN = [  # to Cell 01's biology ontology (read only); logical where the meaning is the same, else not stated
    Sub("Organoid", "bio:Organoid"), Sub("CultureMedium", "bio:CultureMedium"), Sub("Toxicant", "bio:Toxicant"),
    Sub("RescueAgent", "bio:RescueAgent"), Sub("ChallengeAdministration", "bio:ControlledToxicChallenge"),
    Sub("RescueAdministration", "bio:RescueIntervention"), Sub("ImagingAssay", "bio:ImagingProcess"),
    Sub("Incubation", "bio:IncubationProcess"), Sub("Hypothesis", "bio:Hypothesis"), Sub("Prediction", "bio:Prediction"),
    Sub("ProtectiveResponse", "bio:ProtectiveResponse"), Sub("RecoveryProcess", "bio:RecoveryProcess"),
    Sub("CellDeath", "bio:CellDeathProcess"), Sub("CultureGrowth", "bio:CultureGrowth"),
    Sub("InjuryProcess", "bio:DamageAccumulation"), Sub("Plate", "bio:CulturePlate"), Sub("Well", "bio:CultureWell")]


# ================================================================================================= building the OWL ontology
class K:
    """Name -> owlready2 entity, created on first use inside one ontology."""

    def __init__(self, onto, bio=None):
        self.onto, self.bio, self.c, self.p, self.d = onto, bio, {}, {}, {}

    def cls(self, n):
        if n.startswith("bio:"):
            return self.bio[n[4:]]
        if n not in self.c:
            with self.onto:
                self.c[n] = pytypes.new_class(n, (o.Thing,))
        return self.c[n]

    def prop(self, n):
        if n not in self.p:
            with self.onto:
                self.p[n] = pytypes.new_class(n, (o.ObjectProperty,))
        return self.p[n]

    def dprop(self, n):
        if n not in self.d:
            with self.onto:
                self.d[n] = pytypes.new_class(n, (o.DataProperty,))
                self.d[n].range = [float] if n not in ("wellRow",) else [str]
        return self.d[n]


def add_axiom(ax, k):
    with k.onto:
        if isinstance(ax, Eq):
            k.cls(ax.l.n).equivalent_to.append(ax.r.owl(k))
        elif isinstance(ax, Sub):
            if isinstance(ax.l, A) and ax.l.n != "⊤":
                k.cls(ax.l.n).is_a.append(ax.r.owl(k))
            elif isinstance(ax.l, Some) and isinstance(ax.l.c, A) and ax.l.c.n == "⊤" and not isinstance(ax.l.r, Inv):
                k.prop(ax.l.r).domain.append(ax.r.owl(k))           # ∃r.⊤ ⊑ C  is  domain(r) = C
            elif isinstance(ax.l, A) and ax.l.n == "⊤" and isinstance(ax.r, All) and not isinstance(ax.r, Card):
                k.prop(ax.r.r).range.append(ax.r.c.owl(k))          # ⊤ ⊑ ∀r.C  is  range(r) = C
            else:
                o.GeneralClassAxiom(ax.l.owl(k)).is_a.append(ax.r.owl(k))
        elif isinstance(ax, Disj):
            o.AllDisjoint([c.owl(k) for c in ax.cs])
        elif isinstance(ax, SubR):
            k.prop(ax.r).is_a.append(k.prop(ax.s))
        elif isinstance(ax, FuncD):
            k.dprop(ax.r).is_a.append(o.FunctionalProperty)
        elif isinstance(ax, Func):
            k.prop(ax.r).is_a.append(o.FunctionalProperty)
        elif isinstance(ax, Trans):
            k.prop(ax.r).is_a.append(o.TransitiveProperty)
        elif isinstance(ax, InvR):
            k.prop(ax.r).inverse_property = k.prop(ax.s)
        elif isinstance(ax, Chain):
            k.prop(ax.s).property_chain.append(o.PropertyChain([k.prop(r) for r in ax.rs]))


# ================================================================================================= the ABox
class ABox:
    """Facts in the DSL: type assertions (possibly with closure expressions), relations, data values, distinctness."""

    def __init__(self, name, note):
        self.name, self.note = name, note
        self.types, self.rels, self.vals, self.diff = [], [], [], []

    def t(self, i, c):
        self.types.append((i, C(c)))

    def r(self, p, a, b):
        self.rels.append((p, a, b))

    def v(self, p, a, x):
        self.vals.append((p, a, x))

    def different(self, *xs):
        self.diff.append(list(xs))

    def build(self, k):
        ind = {}

        def get(n):
            if n not in ind:
                with k.onto:
                    ind[n] = o.Thing(n, namespace=k.onto)
            return ind[n]
        with k.onto:
            for i, c in self.types:
                get(i).is_a.append(c.owl(k))
            for p, a, b in self.rels:
                k.prop(p)[get(a)].append(get(b))
            for p, a, x in self.vals:
                k.dprop(p)[get(a)].append(x)
            for d in self.diff:
                o.AllDifferent([get(n) for n in d])
        return ind

    def lines(self, m):
        I = (lambda n: n) if m == "txt" else (lambda n: rf"\mathtt{{{n.replace('_', chr(92) + '_' + chr(92) + 'allowbreak{}')}}}")  # noqa: E731
        out = [f"{strip(c.dl(m))}({I(i)})" if isinstance(c, A) else f"({strip(c.dl(m))})({I(i)})" for i, c in self.types]
        out += [f"{rdl(p, m)}({I(a)}, {I(b)})" for p, a, b in self.rels]
        out += [f"{rdl(p, m)}({I(a)}, {x})" for p, a, x in self.vals]
        return out


def schedule(spec, arm):
    """An arm's administrations: the union of its levels' administrations."""
    return [adm for f, lv in spec["arms"][arm]["levels"].items() for adm in spec["factors"][f][lv]]


def contrasted(spec, a, b):
    """The factors in which two arms differ (closed world: every arm has one level of every factor)."""
    return [f for f in spec["factors"] if spec["arms"][a]["levels"][f] != spec["arms"][b]["levels"][f]]


def design_abox(name, spec, note, executed=None):
    """spec: factors {factor: {level: [(agent role, dose, time h), ...]}}, arms {arm: {levels: {factor: level}, units}},
    comparisons {cmp: (arm a, arm b)}, licenses [(cmp, cmp)], rules {cmp: kind}, positive {arm: evidence},
    interaction [(cmp, cmp)], eig, placement, readout, deviation_rule."""
    B = ABox(name, note)
    d = f"{name}_design"
    P = "" if name == "challenge_rescue" else name + "_"      # the improved design's own individuals are prefixed
    B.t(d, "StudyDesign")
    if spec.get("eig") is not None:
        B.v("expectedInformationGain_bits", d, float(spec["eig"]))
    B.t(P + "objective", "Objective")
    B.r("hasObjective", d, P + "objective")
    hyps = {"M1_graded": "GradedRecoveryHypothesis", "M2_threshold": "ThresholdRecoveryHypothesis",
            "M3_protective": "ProtectiveResponseHypothesis"}
    for h, c in hyps.items():
        B.t(h, c)
        B.r("isAbout", P + "objective", h)
    B.different(*hyps)
    agents = {"challenge": "ChallengeAgentRole", "rescue": "RescueAgentRole", "vehicle": "VehicleRole"}
    used = sorted({a for arm in spec["arms"] for a, *_ in schedule(spec, arm)})
    for a in used:
        B.t(f"agent_{a}", "ChemicalAgent")
        B.t(f"role_{a}", agents[a])
        B.r("bearerOf", f"agent_{a}", f"role_{a}")
    if "challenge" in used:
        B.t("toxicity", "ToxicityDisposition")
        B.r("bearerOf", "agent_challenge", "toxicity")
    B.different(*[f"agent_{a}" for a in used])
    # factors and levels
    for f, levels in spec["factors"].items():
        fn = f"{P}factor_{f}"
        B.t(fn, "Factor")
        if spec.get("factor_kinds", {}).get(f):
            B.t(fn, spec["factor_kinds"][f])
        B.r("hasFactor", d, fn)
        for lv in levels:
            B.t(f"{P}level_{f}_{lv}", "FactorLevel")
            B.r("hasLevel", fn, f"{P}level_{f}_{lv}")
        B.different(*[f"{P}level_{f}_{lv}" for lv in levels])
    B.different(*[f"{P}factor_{f}" for f in spec["factors"]])
    # arms: levels, the administrations they specify, the units assigned
    all_units = []
    for arm, a in spec["arms"].items():
        an = f"{P}arm_{arm}"
        B.t(an, "ArmSpecification")
        B.r("hasArm", d, an)
        for f, lv in a["levels"].items():
            B.r("atLevel", an, f"{P}level_{f}_{lv}")
        specs = []
        for ag, dose, t in schedule(spec, arm):
            s = f"{P}admin_{arm}_{ag}_{int(t)}h"
            specs.append(s)
            B.t(s, "AdministrationSpecification")
            B.r("hasAdministrationSpec", an, s)
            B.r("usesAgent", s, f"agent_{ag}")
            B.v("dose_au", s, float(dose))
            B.v("atTime_h", s, float(t))
        B.t(an, Max(len(specs), "hasAdministrationSpec", "AdministrationSpecification"))   # closure
        if specs:
            B.different(*specs)
        units = [f"{P}unit_{arm}_{i + 1}" for i in range(a["units"])]
        for u in units:
            B.t(u, "OrganoidCulture")
            B.t(f"{u}_role", "ExperimentalUnitRole")
            B.r("bearerOf", u, f"{u}_role")
            B.r("assignedTo", u, an)
        B.t(an, Max(len(units), "hasAssignedUnit", "ExperimentalUnit"))
        all_units += units
        if arm in spec.get("positive", {}):
            B.t(f"{P}prior_evidence", "PriorEvidence")
            B.t(f"{P}expectation_{arm}", "Expectation")
            B.r("derivedFrom", f"{P}expectation_{arm}", f"{P}prior_evidence")
            B.r("hasExpectedOutcome", an, f"{P}expectation_{arm}")
    B.different(*all_units)
    B.different(*[f"{P}arm_{a}" for a in spec["arms"]])
    B.t(d, Max(len(spec["arms"]), "hasArm"))                 # closure over every filler, so that ∀hasArm.C is decidable
    # comparisons: the arms compared and the factors contrasted (computed, then closed)
    for c, (a, b) in spec["comparisons"].items():
        cn = f"{P}cmp_{c}"
        B.t(cn, "ComparisonSpecification")
        B.r("hasComparisonSpec", d, cn)
        B.r("compares", cn, f"{P}arm_{a}")
        B.r("compares", cn, f"{P}arm_{b}")
        fs = contrasted(spec, a, b)
        for f in fs:
            B.r("contrasts", cn, f"{P}factor_{f}")
        B.t(cn, Max(len(fs), "contrasts"))
    for a, b in spec["licenses"]:
        B.r("licenses", f"{P}cmp_{a}", f"{P}cmp_{b}")
    B.different(*[f"{P}cmp_{c}" for c in spec["comparisons"]])
    B.t(d, Max(len(spec["comparisons"]), "hasComparisonSpec"))
    for i, (x, y) in enumerate(spec.get("interaction", [])):
        n = f"{P}interaction_{i + 1}"
        B.t(n, "InteractionContrast")
        B.r("hasInteractionContrast", d, n)
        B.r("differenceOf", n, f"{P}cmp_{x}")
        B.r("differenceOf", n, f"{P}cmp_{y}")
    # readout and analysis plan
    B.t(f"{P}viability", "Viability")
    readouts = spec.get("readouts") or [("imaging", spec["readout"]["at_h"])]
    for kind, at_h in readouts:
        rn = f"{P}readout" if kind == "imaging" else f"{P}readout_{kind}"
        q = {"imaging": ("OrganoidSize", "organoid_size"), "luminescence": ("MetabolicActivity", "metabolic_activity"),
             "absorbance": ("MetabolicActivity", "metabolic_activity")}[kind]
        B.t(rn, "ReadoutSpecification")
        B.t(rn, {"imaging": "ImagingReadout", "luminescence": "LuminescenceReadout", "absorbance": "AbsorbanceReadout"}[kind])
        B.r("hasReadout", d, rn)
        B.t(f"{P}{q[1]}", q[0])
        B.r("measures", rn, f"{P}{q[1]}")
        B.r("isProxyFor", rn, f"{P}viability")
        B.v("atTime_h", rn, float(at_h))
    B.t(f"{P}analysis_plan", "AnalysisPlan")
    B.r("hasAnalysisPlan", d, f"{P}analysis_plan")
    kinds = {"threshold": "ThresholdRule", "bayes": "BayesianUpdateRule", "estimate": "EstimationRule"}
    for c, kind in spec["rules"].items():
        rn = f"{P}rule_{c}"
        B.t(rn, kinds[kind[0]])
        B.r("hasDecisionRule", f"{P}analysis_plan", rn)
        B.r("appliesTo", rn, f"{P}cmp_{c}")
        if kind[0] == "bayes":
            for h in hyps:
                B.r("isAbout", rn, h)
        if kind[0] == "threshold":
            B.v("threshold_sd", rn, float(kind[1]))
    if spec.get("deviation_rule"):
        B.t(f"{P}rule_deviations", "DeviationRule")
        B.r("hasDecisionRule", f"{P}analysis_plan", f"{P}rule_deviations")
        B.t(f"{P}rule_deviations", Max(0, "appliesTo"))
    pl = spec.get("placement")
    if pl:
        B.t(pl["plate"], "Plate")
        for u, well in pl["wells"].items():
            w = f"{P}well_{well}"
            B.t(w, "Well")
            B.r("hasWell", pl["plate"], w)
            B.r("contains", w, u)
            B.v("wellRow", w, well[0])
            B.v("wellColumn", w, float(int(well[1:])))
    if executed:
        executed(B, d)
    return B


def current_design():
    """The challenge-rescue experiment of experiment.ldl, derived and placed, with the surrogate run's results. Its
    factors are read off the schedules: one factor per agent, levels 'none' and the administration given."""
    E0 = parse(open(os.path.join(LAB, "experiment.ldl")).read())[0]
    E, _ = derived_and_placed(E0)
    cul = {slot(s[1], "role")[1]: s[1] for s in dslots(E) if s[0] == "culture"}
    sched = {r: [(ex_key(e)[0], float(slot(e, "dose")[1]), float(slot(e, "at")[1][1])) for e in exposures(u)]
             for r, u in cul.items()}
    factors = {}
    for r, adm in sched.items():
        for ag, dose, t in adm:
            factors.setdefault(ag, {"none": []})[f"{dose:g}au_{t:g}h".replace(".", "p")] = [(ag, dose, t)]
    arms = {r: dict(units=1, levels={f: next((f"{dose:g}au_{t:g}h".replace(".", "p") for ag, dose, t in adm if ag == f), "none")
                                     for f in factors}) for r, adm in sched.items()}
    comps, lic, rules = {}, [], {}
    for s in dslots(E):
        if s[0] == "comparison":
            c = s[1]
            comps[role_of(c)] = tuple(role_of(b) for b in slot(c, "between")[1:])
            if slot(c, "licenses"):
                lic.append((role_of(c), role_of(slot(c, "licenses")[1])))
            crit = slot(c, "established-when")
            rules[role_of(c)] = ("bayes",) if slot(c, "updates") else ("threshold", float(slot(crit[1], "by-more-than")[1])) \
                if crit else ("estimate",)
    site = next(s[1] for s in dslots(E) if s[0] == "site")
    wells = {f"unit_{role_of(slot(w[1], 'contains')[1])}_1": slot(w[1], "id")[1] for w in dslots(site) if w[0] == "well"}
    plan = json.load(open(PLAN))["selected"]
    K_ = json.load(open(os.path.join(OUT, "culture_plan.json")))["knowledge"]
    tobs = float(slot(slot(slot(E, "shared-conditions")[1], "observation")[1], "at")[1][1])
    spec = dict(factors=factors, arms=arms, comparisons=comps, licenses=lic, rules=rules, eig=plan["eig_bits"],
                readout=dict(at_h=tobs), deviation_rule=False,
                placement=dict(plate=f"plate_{slot(site, 'id')[1]}", wells=wells))

    def executed(B, d):
        x = "experiment_challenge_rescue"
        B.t(x, "Investigation")
        B.r("executes", x, d)
        phases = {"cultivation": "CultivationPhase", "observation": "ObservationPhase", "analysis": "AnalysisPhase"}
        for p, c in phases.items():
            B.t(f"phase_{p}", c)
            B.r("hasPhase", x, f"phase_{p}")
        B.r("precedes", "phase_cultivation", "phase_observation")
        B.r("precedes", "phase_observation", "phase_analysis")
        B.different(*[f"phase_{p}" for p in phases])
        for ph in (s[1] for s in dslots(E) if s[0] == "phase"):
            pn = ph[1].replace("-phase", "")
            for st in (s[1] for s in dslots(ph) if s[0] == "step"):
                n, kind = f"step_{slot(st, 'name')[1]}", slot(st, "kind")[1]
                B.r("hasStep", f"phase_{pn}", n)
                if kind == "intervention":
                    u, a = role_of(slot(st, "culture")[1]), role_of(slot(st, "substance")[1])
                    B.t(n, "Administration")
                    B.r("executes", n, f"admin_{u}_{a}_{int(float(slot(st, 'at')[1][1]))}h")
                    B.r("hasSpecifiedInput", n, f"agent_{a}")
                    B.r("hasSpecifiedInput", n, f"unit_{u}_1")
                elif kind == "growth":
                    B.t(n, "Incubation")
                    for c in (s[1] for s in dslots(st) if s[0] == "culture"):
                        B.r("hasParticipant", n, f"unit_{role_of(c)}_1")
                elif kind == "observation":
                    u = role_of(slot(st, "culture")[1])
                    B.t(n, "ImagingAssay")
                    B.r("hasSpecifiedInput", n, f"unit_{u}_1")
                    B.t(f"image_{u}", "Image")
                    B.r("hasSpecifiedOutput", n, f"image_{u}")
                    B.r("isAbout", f"image_{u}", f"unit_{u}_1")
                elif kind == "interpretation":
                    u = role_of(slot(st, "about")[1])
                    B.t(n, "ImageAnalysis")
                    B.r("hasSpecifiedInput", n, f"image_{u}")
                    B.t(f"size_{u}", "SizeDatum")
                    B.r("hasSpecifiedOutput", n, f"size_{u}")
                    B.v("radius_um", f"size_{u}", float(K_["observed_radius_um"][{"rescued": "cr", "comparator": "cc", "control": "ck"}[u]]))
                elif kind == "analysis":
                    pair = [role_of(v[1]) for v in slot(st, "statistic")[1][1:]]
                    c = next(c for c, ab in comps.items() if list(ab) == pair)
                    B.t(n, "StatisticalComparison")
                    B.r("executes", n, f"cmp_{c}")
                    B.r("executes", n, f"rule_{c}")
                    B.t(f"effect_{c}", "EffectEstimate")
                    B.r("hasSpecifiedOutput", n, f"effect_{c}")
                    for u in pair:
                        B.r("derivedFrom", f"effect_{c}", f"size_{u}")
                    if slot(st, "updates"):
                        B.t(n, "ModelUpdate")
                        B.t("posterior", "PosteriorDistribution")
                        B.r("hasSpecifiedOutput", n, "posterior")
                        for h in ("M1_graded", "M2_threshold", "M3_protective"):
                            B.r("isAbout", "posterior", h)
        B.v("radius_um", "effect_primary", float(K_["effect_um"]))
        B.v("radius_um", "effect_validity", round(K_["observed_radius_um"]["cc"] - K_["observed_radius_um"]["ck"], 2))
        for h, p in plan["predicted_effect_um"].items():
            B.t(f"prediction_{h}", "Prediction")
            B.r("derivedFrom", f"prediction_{h}", h)
            B.r("isAbout", f"prediction_{h}", "cmp_primary")
            B.v("predictedMean_um", f"prediction_{h}", round(p["effect_um"], 2))
            B.v("predictedSd_um", f"prediction_{h}", round(p["effect_sd_um"], 2))
        B.t("conclusion_answer", "Conclusion")
        B.r("derivedFrom", "conclusion_answer", "posterior")
        B.t("conclusion_rescue_effect", "Conclusion")
        B.r("derivedFrom", "conclusion_rescue_effect", "effect_primary")
        B.t("conclusion_challenge_effect", "Conclusion")
        B.r("derivedFrom", "conclusion_challenge_effect", "effect_validity")
    B = design_abox("challenge_rescue", spec, "the challenge-rescue experiment of experiment.ldl, as derived and placed, "
                    "with the surrogate run's results (ILLUSTRATIVE, D016)", executed)
    return B, spec


def improved_spec(eig3, units=3, positive=True):
    """ILLUSTRATIVE: the reviewer's design as a factorial. Factors: challenge (vehicle, 0.85 au at 0 h) and time of
    rescue (none, 6 h, 48 h), every level vehicle-matched. Arms: vehicle, rescue only, challenge only, challenge with
    late rescue, and challenge with early rescue as the positive control (prior evidence: rescue at 6 h was effective
    at every dose tested). Three replicates per arm, randomised interior wells, analysis plan with a deviation rule."""
    factors = {"challenge": {"vehicle": [("vehicle", 0.0, 0)], "c085": [("challenge", 0.85, 0)]},
               "rescue_time": {"none": [("vehicle", 0.0, 6), ("vehicle", 0.0, 48)],
                               "h6": [("rescue", 0.70, 6), ("vehicle", 0.0, 48)],
                               "h48": [("vehicle", 0.0, 6), ("rescue", 0.70, 48)]}}
    arms = {"vehicle": ("vehicle", "none"), "rescue_only": ("vehicle", "h48"), "challenge_only": ("c085", "none"),
            "challenge_late_rescue": ("c085", "h48"), "challenge_early_rescue": ("c085", "h6")}
    if not positive:
        arms.pop("challenge_early_rescue")
    arms = {a: dict(units=units, levels=dict(challenge=c, rescue_time=r)) for a, (c, r) in arms.items()}
    comps = {"validity": ("challenge_only", "vehicle"), "primary": ("challenge_late_rescue", "challenge_only"),
             "agent_alone": ("rescue_only", "vehicle")}
    rules = {"validity": ("threshold", 2.0), "primary": ("bayes",), "agent_alone": ("estimate",)}
    lic = [("validity", "primary")]
    if positive:
        comps.update(positive_control=("challenge_early_rescue", "challenge_only"),
                     window=("challenge_late_rescue", "challenge_early_rescue"))
        rules.update(positive_control=("threshold", 2.0), window=("estimate",))
        lic += [("positive_control", "primary"), ("validity", "window")]
    interior = [f"{r}{c:02d}" for r in "BCDEFG" for c in range(2, 12)]
    import random
    rnd = random.Random(17)
    unames = [f"improved_unit_{a}_{i + 1}" for a in arms for i in range(units)]
    return dict(factors=factors, arms=arms, comparisons=comps, licenses=lic, rules=rules,
                interaction=[("primary", "agent_alone")], positive={"challenge_early_rescue": "rescue at 6 h effective"}
                if positive else {}, eig=eig3, readout=dict(at_h=72), deviation_rule=True,
                placement=dict(plate="plate_P18", wells=dict(zip(unames, rnd.sample(interior, len(unames))))))


def improved_design(eig3):
    spec = improved_spec(eig3)
    return design_abox("improved", spec, "ILLUSTRATIVE improved design (not run): a challenge x time-of-rescue factorial, "
                       "vehicle-matched, rescue-only and early-rescue (positive control) arms, 3 replicates per arm, "
                       "randomised interior wells, pre-specified analysis; information gain for n = 3 from the same "
                       "surrogate (primary contrast only)"), spec


# ================================================================================================= reasoning and closed-world checks
def build(boxes, with_bio=False, extra=None):
    w = o.World()
    onto = w.get_ontology(XP)
    bio = None
    if with_bio:
        xml = os.path.join(DST, "aicor-biology.rdf")
        bio = w.get_ontology("file://" + xml).load()
    k = K(onto, bio)
    for s in tbox():
        for ax in s["axioms"]:
            add_axiom(ax, k)
    if with_bio:
        for ax in ALIGN:
            add_axiom(ax, k)
    inds = {}
    for b in boxes:
        inds.update(b.build(k))
    if extra:
        extra(k, inds)
    return w, onto, k, inds


def reason(w, onto, extra_ontos=()):
    t = time.time()
    try:
        o.sync_reasoner_hermit([onto, *extra_ontos], infer_property_values=False, debug=0)
    except o.OwlReadyInconsistentOntologyError:
        return False, round(time.time() - t, 2), []
    return True, round(time.time() - t, 2), [c.name for c in w.inconsistent_classes()]


def told(n):
    """Named superclasses stated directly: the atoms among the top-level conjuncts of n's own axioms, and their told
    superclasses."""
    out, todo = set(), [n]
    while todo:
        x = todo.pop()
        for s in tbox():
            for ax in s["axioms"]:
                if isinstance(ax, Sub) and isinstance(ax.l, A) and ax.l.n == x:
                    for c in (ax.r.xs if isinstance(ax.r, And) else [ax.r]):
                        if isinstance(c, A) and c.n not in out and c.n not in ("⊤",):
                            out.add(c.n)
                            todo.append(c.n)
    return out


def most_specific(ind, k):
    named = [c for c in ind.is_a if isinstance(c, o.ThingClass) and c.namespace.base_iri == XP]
    return sorted(c.name for c in named if not any(d is not c and issubclass(d, c) for d in named))


def closed_world(B, spec):
    """Checks under the closed world (over the design as given): what OWL 2 DL cannot state or cannot conclude."""
    import itertools
    res = []
    F = spec["factors"]
    arms = spec["arms"]
    res.append(dict(check="every arm has one level of every factor", ok=all(set(a["levels"]) == set(F) for a in arms.values()),
                    detail=f"{len(arms)} arms × {len(F)} factors"))
    for c, (a, b) in spec["comparisons"].items():
        fs = contrasted(spec, a, b)
        ta = {t: (ag, d) for ag, d, t in schedule(spec, a)}
        tb = {t: (ag, d) for ag, d, t in schedule(spec, b)}
        diff = sorted(t for t in set(ta) | set(tb) if ta.get(t) != tb.get(t))
        own = {t for f in fs for lv in F[f].values() for _, _, t in lv}
        res.append(dict(check=f"single factor: {c}", ok=len(fs) == 1,
                        detail=f"{a} vs {b} differ in {', '.join(fs) or 'nothing'}"))
        env = any(spec.get("factor_kinds", {}).get(f) == "EnvironmentFactor" for f in fs)
        res.append(dict(check=f"schedules matched: {c}", ok=(not diff) if env else (bool(diff) and set(diff) <= own),
                        detail=f"administrations differ at {', '.join(f'{t:g} h' for t in diff)}, "
                               f"{'all' if set(diff) <= own else 'not all'} belonging to the contrasted factor"))
    cells = list(itertools.product(*[list(v) for v in F.values()]))
    present = {tuple(a["levels"][f] for f in F) for a in arms.values()}
    missing = [dict(zip(F, c)) for c in cells if c not in present]
    res.append(dict(check="full factorial (information, not required)", ok=not missing, info=True,
                    detail=f"{len(present)} of {len(cells)} level combinations" + (
                        f"; missing: {'; '.join(', '.join(f'{f}={v}' for f, v in m.items()) for m in missing)}" if missing else "")))
    # interaction of two factors is estimable when some 2x2 sub-table of their levels is complete
    names = list(F)
    inter = []
    for f, g in itertools.combinations(names, 2):
        for (l1, l2) in itertools.combinations(F[f], 2):
            for (m1, m2) in itertools.combinations(F[g], 2):
                sub = {(x, y) for x in (l1, l2) for y in (m1, m2)}
                if sub <= {(a["levels"][f], a["levels"][g]) for a in arms.values()}:
                    inter.append(f"{f} {l1}/{l2} × {g} {m1}/{m2}")
    res.append(dict(check="interaction estimable", ok=bool(inter), detail="; ".join(inter[:2]) or "no complete 2×2 sub-table"))
    covered = [c for c in spec["comparisons"] if c in spec["rules"]]
    res.append(dict(check="every comparison has a decision rule", ok=len(covered) == len(spec["comparisons"]),
                    detail=f"{len(covered)} of {len(spec['comparisons'])}"))
    res.append(dict(check="positive control licenses the primary comparison",
                    ok=any(a in ("positive_control",) and b == "primary" for a, b in spec["licenses"]),
                    detail="present" if spec.get("positive") else "no positive-control arm"))
    reps = {a: v["units"] for a, v in arms.items()}
    res.append(dict(check=f"replicates ≥ {MIN_REPLICATES} per arm", ok=all(n >= MIN_REPLICATES for n in reps.values()),
                    detail=", ".join(f"{a} {n}" for a, n in reps.items())))
    edge = sorted({a.split("well_")[1] for p, a, x in B.vals
                   if (p == "wellRow" and x in "AH") or (p == "wellColumn" and int(x) in (1, 12))})
    n_w = len([w for p, a, w in B.rels if p == "contains"])
    res.append(dict(check="units off the plate edge", ok=not edge, detail=f"edge wells: {edge}" if edge else f"{n_w} interior wells"))
    plates = {a for p, a, b in B.rels if p == "hasWell"}
    res.append(dict(check="all units on one plate", ok=len(plates) == 1, detail=", ".join(sorted(plates))))
    ex = [b for p, a, b in B.rels if p == "executes" and "admin_" in b]
    specs = [i for i, c in B.types if isinstance(c, A) and c.n == "AdministrationSpecification"]
    if ex:
        res.append(dict(check="each administration specification executed once", ok=sorted(ex) == sorted(specs),
                        detail=f"{len(ex)} administrations for {len(specs)} specifications"))
    return res


NEGATIVE = {  # each must make the reasoner find the ABox inconsistent
    "a well as part of an arm (parthood crosses kinds)":
        lambda k, i: k.prop("hasPart")[i["arm_control"]].append(i["well_A01"]),
    "a culture assigned to two arms (assignedTo is functional)":
        lambda k, i: k.prop("assignedTo")[i["unit_rescued_1"]].append(i["arm_comparator"]),
    "an administration added to the untreated arm (closure)":
        lambda k, i: k.prop("hasAdministrationSpec")[i["arm_control"]].append(i["admin_rescued_rescue_48h"]),
    "the graded hypothesis posits a loss of recovery capacity":
        lambda k, i: k.prop("posits")[i["M1_graded"]].append(k.cls("LossOfRecoveryCapacity")("loss_1", namespace=k.onto)),
    "the challenge agent also bears the rescue role (disjoint agents)":
        lambda k, i: k.prop("bearerOf")[i["agent_challenge"]].append(i["role_rescue"]),
    "one decision rule applied to two comparisons":
        lambda k, i: k.prop("appliesTo")[i["rule_validity"]].append(i["cmp_primary"]),
    "an incubation function realized in an imaging assay":
        lambda k, i: k.prop("realizedIn")[k.cls("IncubationFunction")("f_bad", namespace=k.onto)].append(i["step_o1"]),
    "a factor level that is also an arm (disjoint plan parts)":
        lambda k, i: i["level_rescue_none"].is_a.append(k.cls("ArmSpecification")),
}


# ================================================================================================= renderings
def render_ofn(boxes):
    out = ["Prefix(xp:=<https://aicor.example/okf/experiment#>)", "Prefix(bio:=<https://aicor.example/okf/biology#>)",
           "Prefix(owl:=<http://www.w3.org/2002/07/owl#>)", "Prefix(xsd:=<http://www.w3.org/2001/XMLSchema#>)",
           "Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)", "",
           "Ontology(<https://aicor.example/okf/experiment>",
           'Annotation(rdfs:comment "Experiments as biomedical experiments (OWL 2 DL). Generated by rsa/experiment_ontology.py. '
           'ILLUSTRATIVE design criteria and values (D016).")']
    for p in OBJ_PROPS:
        out.append(f"Declaration(ObjectProperty(xp:{p}))")
    for p in DATA_PROPS:
        out.append(f"Declaration(DataProperty(xp:{p}))")
    for s in tbox():
        out.append(f"\n# {s['title']}")
        out += [ax.ofn() for ax in s["axioms"]]
    out.append("\n# alignment to Cell 01's biology ontology")
    out += [ax.ofn() for ax in ALIGN]
    for b in boxes:
        out.append(f"\n# ABox: {b.note}")
        for i, c in b.types:
            out.append(f"ClassAssertion({c.ofn()} xp:{i})")
        for p, a, x in b.rels:
            out.append(f"ObjectPropertyAssertion(xp:{p} xp:{a} xp:{x})")
        for p, a, x in b.vals:
            lit = f'"{x}"^^xsd:string' if isinstance(x, str) else f'"{x}"^^xsd:decimal'
            out.append(f"DataPropertyAssertion(xp:{p} xp:{a} {lit})")
        for d in b.diff:
            out.append("DifferentIndividuals(" + " ".join(f"xp:{n}" for n in d) + ")")
    return "\n".join(out) + "\n)\n"


def brk(x):
    for s in (" ⊓ ", " ⊔ "):
        x = x.replace(s, s.rstrip() + r"\allowbreak ")
    return x


def fig_inferred(w, onto, k, path, results):
    """The inferred hierarchy of the defined design concepts, with the two designs' arms, comparisons and designs."""
    show = ["ArmSpecification", "NegativeControlArm", "UntreatedArm", "VehicleControlArm", "ChallengeOnlyArm",
            "RescueOnlyArm", "ChallengeRescueArm", "PositiveControlArm", "ReplicatedArm", "ComparisonSpecification",
            "InjuryValidityComparison", "RescueEffectComparison", "AgentAloneComparison", "PositiveControlComparison",
            "SingleFactorComparison", "RescueTimingComparison", "StudyDesign", "ComparativeDesign", "ControlledDesign",
            "InjuryRescueDesign", "ValidatedInjuryRescueDesign", "AgentControlledInjuryRescueDesign", "TherapeuticWindowDesign",
            "ReplicatedDesign", "PositiveControlledDesign", "WellContrastedDesign", "PreSpecifiedDesign", "FactorialDesign",
            "AdequatelyControlledInjuryRescueDesign", "HypothesisDiscriminatingDesign", "SufficientlyInformativeDesign"]
    dot = ["digraph H { rankdir=BT; nodesep=0.2; ranksep=0.35; node [shape=box, style=rounded, fontname=Helvetica, fontsize=10];"
           " edge [color=\"#555555\"];"]
    for n in show:
        dot.append(f'"{n}";')
        c = k.cls(n)
        sups = [s for s in c.ancestors() if s is not c and s.name in show]
        direct = [s for s in sups if not any(t is not s and issubclass(t, s) for t in sups)]
        for s in direct:
            dot.append(f'"{n}" -> "{s.name}";')
    colors = {"challenge_rescue": "#e3f2fd", "improved": "#fff3e0"}
    for design, r in results.items():
        for ind, types in r["realization"].items():
            if not (ind.split("improved_")[-1].startswith(("arm_", "cmp_")) or ind.endswith("_design")):
                continue
            node = f"{design}:{ind}"
            dot.append(f'"{node}" [label="{ind}", shape=note, style=filled, fillcolor="{colors[design]}", fontsize=8];')
            for t in types:
                if t in show:
                    dot.append(f'"{node}" -> "{t}" [style=dashed, color="#90a4ae", arrowsize=0.5];')
    dot.append("}")
    for fmt_ in ("pdf", "png", "svg"):
        subprocess.run(["dot", f"-T{fmt_}", "-Gdpi=110", "-o", path + "." + fmt_], input="\n".join(dot), text=True, check=True)


def fig_framework(path):
    """The five layers of the framework and the relations between them."""
    layers = [("epistemic", "EPISTEMIC", "question · hypotheses · predictions · belief · objective · conclusions", "#ede7f6"),
              ("design", "DESIGN", "units · factors / levels · arms · controls · replicates · allocation · readouts · comparisons · analysis plan", "#e3f2fd"),
              ("protocol", "PROTOCOL", "methods for administration, incubation, assay, analysis (device-independent, with tolerances)", "#e0f2f1"),
              ("execution", "EXECUTION", "experiment run → phases → steps · participants · times · deviations · lab refinement · audit trail", "#fff3e0"),
              ("system", "BIOLOGICAL SYSTEM", "cultures · organoids · cells · medium · agents (roles, dispositions) · qualities · biological processes", "#fce4ec")]
    dot = ["digraph F { rankdir=TB; nodesep=0.3; ranksep=0.45; node [shape=box, style=\"rounded,filled\", fontname=Helvetica, "
           "fontsize=10, width=7.2]; edge [fontname=Helvetica, fontsize=9];"]
    for n, t, d, c in layers:
        dot.append(f'{n} [label=<<b>{t}</b><br/><font point-size="9">{d}</font>>, fillcolor="{c}"];')
    down = [("epistemic", "design", "addressed by"), ("design", "protocol", "detailed by"), ("protocol", "execution", "executed as"),
            ("execution", "system", "intervenes on · observes")]
    up = [("system", "execution", "data (proxies)"), ("execution", "design", "effect estimates"), ("design", "epistemic", "belief update")]
    for a, b, l in down:
        dot.append(f'{a} -> {b} [label="  {l}", color="#455a64"];')
    for a, b, l in up:
        dot.append(f'{a} -> {b} [label="  {l}", color="#c62828", fontcolor="#c62828", style=dashed, constraint=false];')
    dot.append("}")
    for fmt_ in ("pdf", "png"):
        subprocess.run(["dot", f"-T{fmt_}", "-Gdpi=120", "-o", path + "." + fmt_], input="\n".join(dot), text=True, check=True)


FRAMEWORK = r"""
\part*{I\quad A conceptual framework for biomedical experiments}
\section*{Core idea}
\emph{An experiment is a planned process that intervenes on and observes a biological system, executing a design, in
order to change a belief about hypotheses.} The framework keeps apart what is \emph{planned} (design, protocol), what
\emph{happens} (execution), what is \emph{measured} (data) and what is \emph{believed} (hypotheses, belief,
conclusions); the biology is the hidden state in between, reached only through interventions and through readouts that
are proxies for it. No biological fact or parameter is asserted: hypotheses \emph{posit} biology, data are
\emph{proxies} (D016).

\begin{center}\includegraphics[width=0.92\linewidth]{framework.pdf}\end{center}

\section*{Core concepts}
{\small\begin{tabularx}{\linewidth}{@{}>{\raggedright\arraybackslash}p{3.1cm}>{\raggedright\arraybackslash}X@{}}\toprule
Experimental unit & what is treated independently and measured (a culture in a well) \\
Factor, level & what is varied (agent, dose, time of rescue) and the values it takes \\
Treatment & one combination of levels, given as a schedule of administrations \\
Arm & a treatment and the units assigned to it (membership, not parthood) \\
Control & an arm defined by what it controls for: negative (untreated, vehicle), positive (expected effect from prior
evidence), agent-alone (the agent's own effect), comparator (isolates one factor) \\
Replicate & units under the same treatment; biological (independent units) vs technical (repeated measurements) \\
Allocation & assignment and placement of units: randomisation, blocking, avoiding edge wells, blinding \\
Readout & the measured quantity, its time and assay, and what it is a proxy for (size for viability) \\
Comparison & a pair of arms whose difference estimates the effect of exactly one factor \\
Interaction contrast & a difference of comparisons: does a factor's effect depend on another factor \\
Validity check & a comparison that licenses another (injury happened; the agent works) \\
Analysis plan & the decision rule of every comparison and the handling of deviations, fixed before the run \\
Hypothesis, prediction & a model that posits processes, and its expected effect for a comparison \\
Belief, information gain & a probability over hypotheses, and how much a design is expected to change it \\
Deviation & a difference between execution and plan; it can invalidate comparisons \\
Conclusion (insight) & a statement derived from effect estimates and the posterior, with provenance \\
\bottomrule\end{tabularx}}

\section*{Taxonomy along independent axes}
System (in silico, in vitro, ex vivo, in vivo, clinical); purpose (exploratory, confirmatory, hypothesis-discriminating,
dose--response, time-course); design structure (comparative, controlled, factorial, within- or between-unit,
randomised, blinded); intervention (challenge, rescue or therapy, both); adequacy (validated, agent-controlled,
positive-controlled, replicated, pre-specified). Classes are \emph{defined}, so a reasoner places an experiment under
every class it satisfies (Part~II).

\section*{Criteria and how each is enforced}
{\small\begin{tabularx}{\linewidth}{@{}>{\raggedright\arraybackslash}p{2.2cm}>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}p{4.6cm}@{}}\toprule
validity & criteria & enforced by \\ \midrule
internal & single factor per comparison; negative, agent-alone and positive controls; randomisation; blinding & defined classes (reasoner); closed-world checks \\
statistical & biological replicates; expected information or power & closed-world counts; information-gain model \\
construct & readout states its proxy relation; manipulation checked (validity comparison) & ontology; licensing order in the plan \\
executional & identity, contamination, environment kept; plan realized; deviations recorded & run-time monitors (CRAM); audit trail \\
external & relevance of the system to the target biology & stated as an assumption, never inferred \\
\bottomrule\end{tabularx}}

\emph{Description logic for what experiments are; closed-world queries for what a design must contain; run-time monitors
for what an execution must keep; probabilistic models for what it will tell us.}

\section*{Lifecycle}
Question $\rightarrow$ hypotheses and predictions $\rightarrow$ candidate designs $\rightarrow$ selection (information vs
cost) $\rightarrow$ \textbf{adequacy check before the run} $\rightarrow$ protocol $\rightarrow$ refinement into lab actions
$\rightarrow$ monitored execution $\rightarrow$ data $\rightarrow$ analysis by the pre-specified rules $\rightarrow$ belief
update $\rightarrow$ conclusions $\rightarrow$ next question. Foundations: BFO-style upper level, OBI patterns (planned
process, study design, assay), Cell~01's biology ontology for the domain.

\part*{II\quad The axiomatization}
"""


def tex_doc(results, neg, bio_res, boxes, inferred_subs, variants):
    S = tbox()
    out = [r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=2.1cm]{geometry}
\usepackage{fontspec,unicode-math}
\setmainfont{Libertinus Serif}\setsansfont{IBM Plex Sans}[Scale=0.9]\setmonofont{IBM Plex Mono}[Scale=0.82]
\setmathfont{Libertinus Math}
\usepackage{graphicx,booktabs,tabularx,multicol,xcolor,hyperref,enumitem,array}
\hypersetup{colorlinks,linkcolor=black,urlcolor=blue!50!black}
\newcommand{\ax}[1]{\par{\raggedright\noindent\hangindent=2.5em\hangafter=1 $#1$\par}\smallskip}
\setlength{\parindent}{0pt}\setlength{\parskip}{3pt}\setlength{\emergencystretch}{3em}
\title{A conceptual framework for biomedical experiments\\[2pt]\large and its OWL~2~DL axiomatization, classified by a reasoner}
\author{Generated by \texttt{rsa/experiment\_ontology.py}; all values ILLUSTRATIVE (D016)}
\date{}
\begin{document}\maketitle
""" + FRAMEWORK + r"""
\section*{What Part II is}
The challenge-rescue experiment axiomatized as a biomedical experiment in $\mathcal{SROIQ}(\mathbf{D})$ (OWL~2~DL).
One source gives the DL notation below, an OWL ontology (\texttt{experiment.ofn}, \texttt{experiment.owl}) and the
input of the HermiT reasoner, which checks consistency, classifies the concepts and realizes the individuals.
Compared with the first axiomatization, the design is a \emph{plan} that the experiment executes; cultures are
\emph{units assigned to arms} (membership, not parthood); agents are chemical entities bearing \emph{roles} and
\emph{dispositions}; arms, comparisons, designs and experiments are \emph{defined} concepts that the reasoner
classifies from their content; the biomedical adequacy of a design is part of the hierarchy; hypotheses are
information entities that \emph{posit} processes, so nothing biological is asserted as fact; size is a
\emph{proxy} for viability. Concepts are set in $\mathsf{sans}$, roles in $\mathit{italics}$, individuals in
$\mathtt{mono}$.
"""]
    for i, s in enumerate(S, 1):
        out.append(rf"\section{{{s['title']}}}{s['text']}")
        cols = len(s["axioms"]) > 12 and s["title"] in ("Upper level", "Relations and partonomy")
        if cols:
            out.append(r"\begin{multicols}{2}")
        for ax in s["axioms"]:
            out.append(rf"\ax{{{brk(ax.dl('tex'))}}}")
            if ax.note:
                out.append(rf"{{\footnotesize\itshape\quad {ax.note}}}\par")
        if cols:
            out.append(r"\end{multicols}")
    out.append(r"\section{Alignment to Cell~01's biology ontology}")
    out.append("Where a concept means the same as one of \\texttt{aicor-biology.ttl} (read only), it is subsumed by it. "
               f"Joint reasoning: {'consistent' if bio_res['consistent'] else 'INCONSISTENT'}, "
               f"{len(bio_res['unsat'])} unsatisfiable concepts" + (f" ({', '.join(bio_res['unsat'])})" if bio_res["unsat"] else "")
               + f", HermiT {bio_res['seconds']} s.")
    out.append(r"\begin{multicols}{2}")
    out += [rf"\ax{{{ax.dl('tex')}}}" for ax in ALIGN]
    out.append(r"\end{multicols}")
    out.append(r"\section{What OWL~2~DL cannot state: closed-world checks}")
    out.append("Single difference compares two arms' administration schedules; replication counts units; edge "
               "placement and one-plate placement compare values reached by different paths; whether every "
               "specification was executed needs the closed world. These are queries over the reasoned ABox "
               "(Section~\\ref{sec:results}).")
    out.append(r"\section{Reasoning results}\label{sec:results}")
    for name, r in results.items():
        out.append(rf"\subsection*{{{tex(boxes[name].note[0].upper() + boxes[name].note[1:])}}}")
        out.append(rf"HermiT: {'consistent' if r['consistent'] else 'INCONSISTENT'}, "
                   rf"{len(r['unsat'])} unsatisfiable concepts, {r['seconds']} s.")
        out.append(r"\par\noindent\begin{tabularx}{\linewidth}{@{}>{\raggedright\arraybackslash}p{4.2cm}>{\raggedright\arraybackslash}X@{}}"
                   r"\toprule individual & inferred most specific concepts \\ \midrule")
        for ind, ts in r["realization"].items():
            out.append(rf"\texttt{{{tex(ind).replace(chr(92) + '_', chr(92) + '_' + chr(92) + 'allowbreak{}')}}} & "
                       rf"{', '.join(rf'$\mathsf{{{t}}}$' for t in ts)} \\")
        out.append(r"\bottomrule\end{tabularx}")
        out.append(r"\par\smallskip Closed-world checks:\begin{itemize}[nosep]")
        for c in r["closed_world"]:
            out.append(rf"\item {'information' if c.get('info') else '\\textcolor{green!50!black}{pass}' if c['ok'] else '\\textcolor{red!70!black}{fail}'}: "
                       rf"{tex(c['check'])} ({tex(c['detail'])})")
        out.append(r"\end{itemize}")
    out.append(r"\begin{center}\includegraphics[width=\linewidth]{inferred.pdf}\end{center}")
    out.append(r"{\small The inferred hierarchy of the defined design concepts (solid) and the realization of the two "
               r"designs' arms, comparisons and designs (dashed; blue: current, orange: improved).}")
    out.append(r"\subsection*{Variants of the improved design}")
    out.append(r"{\small\begin{tabularx}{\linewidth}{@{}>{\raggedright\arraybackslash}p{4.6cm}>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}X@{}}"
               r"\toprule variant & most specific design concepts & closed-world checks failed \\ \midrule")
    for v, r in variants.items():
        out.append(rf"{tex(v)} & {', '.join(rf'$\mathsf{{{t}}}$' for t in r['design'])} & {tex('; '.join(r['failed'])) or '---'} \\")
    out.append(r"\bottomrule\end{tabularx}}")
    out.append(r"\subsection*{Inferred subsumptions not stated as axioms}")
    out.append(r"\begin{itemize}[nosep]" + "".join(rf"\item $\mathsf{{{a}}} \sqsubseteq \mathsf{{{b}}}$" for a, b in inferred_subs)
               + r"\end{itemize}")
    out.append(r"\subsection*{Negative controls (each must be inconsistent)}\begin{itemize}[nosep]")
    for n, ok in neg.items():
        out.append(rf"\item {tex(n)}: {'inconsistent, as required' if ok else '\\textbf{NOT detected}'}")
    out.append(r"\end{itemize}")
    out.append(r"\section{ABox of the challenge-rescue experiment (excerpt)}")
    out.append(r"{\footnotesize\begin{multicols}{2}")
    lines = boxes["challenge_rescue"].lines("tex")
    out += [rf"${x}$\par" for x in lines[:150]]
    out.append(r"\end{multicols}}")
    out.append(r"\end{document}")
    return "\n".join(out)


def tex(s):
    return s.replace("_", r"\_").replace("&", r"\&").replace("%", r"\%").replace("#", r"\#").replace("≥", r"$\geq$")


def main(argv):
    os.makedirs(DST, exist_ok=True)
    import rdflib
    g = rdflib.Graph()
    g.parse(BIO_TTL)
    g.serialize(os.path.join(DST, "aicor-biology.rdf"), format="xml")
    plan = json.load(open(PLAN))
    eig3 = plan["candidate_eig_bits"].get("c_d85_t48_n3")
    B1, spec1 = current_design()
    B2, spec2 = improved_design(eig3)
    boxes = {"challenge_rescue": B1, "improved": B2}
    results = {}
    for name, (B, spec) in {"challenge_rescue": (B1, spec1), "improved": (B2, spec2)}.items():
        w, onto, k, inds = build([B])
        stated = {n: {s.name for s in c.ancestors() if s.namespace.base_iri == XP} | told(n) for n, c in k.c.items()}
        ok, secs, unsat = reason(w, onto)
        keep = [i for i in inds if i.split("improved_")[-1].startswith(("arm_", "cmp_", "experiment_")) or i.endswith(("_design", "objective"))
                or i in ("agent_challenge", "agent_rescue", "agent_vehicle", "step_x1", "step_x3", "step_a1")]
        real = {i: most_specific(inds[i], k) for i in keep}
        results[name] = dict(consistent=ok, seconds=secs, unsat=unsat, realization=real, closed_world=closed_world(B, spec))
        if name == "challenge_rescue":
            inferred = []
            for n, c in k.c.items():
                new = [s for s in c.ancestors() if s is not c and s.namespace.base_iri == XP and s.name not in stated[n]]
                direct = [s for s in new if not any(t is not s and issubclass(t, s) for t in new)]
                inferred += [(n, s.name) for s in direct]
            fig_inferred(w, onto, k, os.path.join(DST, "inferred"), {})
        print(f"[owl] {name}: HermiT {'consistent' if ok else 'INCONSISTENT'} in {secs} s, unsatisfiable {unsat}")
        for i, ts in real.items():
            print(f"        {i:28} {', '.join(ts)}")
        for c in results[name]["closed_world"]:
            print(f"        {'info' if c.get('info') else 'pass' if c['ok'] else 'FAIL'}  {c['check']}: {c['detail']}")
    # variants of the improved design: what the reasoner concludes when one ingredient is missing
    variants = {}
    for label, sp in {"improved without the positive-control arm": improved_spec(eig3, positive=False),
                      "improved with one unit per arm": improved_spec(eig3, units=1),
                      "improved without a pre-specified analysis": dict(improved_spec(eig3), rules={}, deviation_rule=False)}.items():
        Bv = design_abox("variant", sp, label)
        w, onto, k, inds = build([Bv])
        okv, _, _ = reason(w, onto)
        variants[label] = dict(consistent=okv, design=most_specific(inds["variant_design"], k),
                               failed=[c["check"] for c in closed_world(Bv, sp) if not c["ok"] and not c.get("info")])
        print(f"[variant] {label:45} {', '.join(variants[label]['design'])}; closed-world fails {variants[label]['failed']}")
    # the figure needs both realizations: rebuild once with both designs
    w, onto, k, inds = build([B1, B2])
    ok_both, _, _ = reason(w, onto)
    print(f"[owl] both designs in one ABox: {'consistent' if ok_both else 'INCONSISTENT'}")
    fig_inferred(w, onto, k, os.path.join(DST, "inferred"), results)
    # joint consistency with Cell 01's biology ontology
    w, onto, k, inds = build([B1], with_bio=True)
    okb, secb, unsb = reason(w, onto, [k.bio])
    bio_res = dict(consistent=okb, seconds=secb, unsat=unsb)
    print(f"[owl] with Cell 01 biology ontology: {'consistent' if okb else 'INCONSISTENT'} in {secb} s, unsatisfiable {unsb}")
    base_ok = results["challenge_rescue"]["consistent"] and not results["challenge_rescue"]["unsat"]
    neg = {}
    for n, f in NEGATIVE.items():
        w, onto, k, inds = build([B1], extra=f)
        okn, _, _ = reason(w, onto)
        neg[n] = base_ok and not okn       # meaningful only against a consistent base
        print(f"[negative] {n:66} {'inconsistent, as required' if neg[n] else ('NOT DETECTED' if base_ok else 'void: base inconsistent')}")
    # the class hierarchy facts the reasoner derived (no stated axiom says them)
    subs = sorted(set(inferred))
    print(f"[owl] inferred subsumptions not stated: {subs[:12]}{' ...' if len(subs) > 12 else ''}")
    open(os.path.join(DST, "experiment.ofn"), "w").write(render_ofn([B1, B2]))
    w, onto, k, inds = build([B1, B2])
    onto.save(os.path.join(DST, "experiment.owl"), format="rdfxml")
    txt = []
    for s in tbox():
        txt += ["", s["title"].upper()] + ["  " + ax.dl("txt") for ax in s["axioms"]]
    txt += ["", "ALIGNMENT"] + ["  " + ax.dl("txt") for ax in ALIGN]
    open(os.path.join(DST, "experiment_tbox.txt"), "w").write("\n".join(txt).strip() + "\n")
    fig_framework(os.path.join(DST, "framework"))
    t = tex_doc(results, neg, bio_res, boxes, subs, variants)
    open(os.path.join(DST, "experiment_owl.tex"), "w").write(t)
    p = subprocess.run(["latexmk", "-lualatex", "-interaction=nonstopmode", "-halt-on-error", "experiment_owl.tex"],
                       cwd=DST, capture_output=True, text=True)
    log = open(os.path.join(DST, "experiment_owl.log"), errors="replace").read() if os.path.exists(os.path.join(DST, "experiment_owl.log")) else ""
    pages = re.search(r"Output written on .*?\((\d+) pages?", log)
    over = len(re.findall(r"Overfull \\hbox", log))
    json.dump(dict(results=results, negative_controls=neg, with_bio=bio_res, inferred_subsumptions=subs, variants=variants),
              open(os.path.join(DST, "experiment_owl.json"), "w"), indent=1)
    print(f"[owl] latex exit {p.returncode}, {pages.group(1) if pages else '?'} pages, {over} overfull -> {os.path.relpath(DST)}/")
    if p.returncode:
        print(p.stdout[-2500:])
    good = (all(r["consistent"] and not r["unsat"] for r in results.values()) and all(neg.values()) and okb and p.returncode == 0)
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
