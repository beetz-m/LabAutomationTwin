---
type: concept
title: "CriticGateMechanism"
description: "Enforcement by Cell 01's critic vector: an event commits only if safety_ok (AICOR commitment checking)."
source:
  - "ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff/sdt/schemas/critic_vector_schema.yaml"
  - "ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff/biology/ontology/monitoring-rules.yaml"
  - "ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff/biology/ontology/contamination-and-asepsis.md"
  - "LabAutomationTwin/twin/site_doors.py"
  - "LabAutomationTwin/scripts/test_*.py"
maturity: L1
status: draft
timestamp: 2026-10-17
l2: lab-twin-safe-action-dl.md
---
# CriticGateMechanism

✅ Enforcement by Cell 01's critic vector: an event commits only if safety_ok (AICOR commitment checking).

🔧 **Grounding** — specialises `dul_Description`, `SafetyCheck`. Defined in L2 [`lab-twin-safe-action-dl.md`](../../../L2-conceptual-framework/ontology/lab-twin-safe-action-dl.md) (Safe action: hazards, safety rules, enforcement, admissibility of candidate actions).

