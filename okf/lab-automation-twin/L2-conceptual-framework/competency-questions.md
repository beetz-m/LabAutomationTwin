---
type: competency-questions
title: "lab-automation-twin competency questions"
---
# Competency questions

TBox questions are executable (`competency-questions.yaml`, `make cq`); ABox questions over the twin are answered by `check_module.py` into `../docs/competency_questions.md`.

## Answered by the L2 (executable)

**CQ-1** Is Cell 01's automated incubator an AICOR lab-automation device and an incubation device?

**CQ-2** Is a device manual's operating procedure an AICOR / robot-scientist action contract?

**CQ-3** Is a device failure mode an AICOR failure signature, recovered by a repair?

**CQ-4** Is a recovery procedure an AICOR Repair?

**CQ-5** Is a lab safety rule a universal prohibition (AICOR IncapabilityAssertion, a BodyWorldConstraint)?

**CQ-6** Is a biosafety rule a contamination-compatibility gate on interventions?

**CQ-7** Is an authorisation rule a norm rather than a causal safety prohibition?

**CQ-8** Can an SDT node be the physical thing it represents?

**CQ-9** Is a culture experiment run an AICOR manipulation episode?

**CQ-10** Does the challenge-rescue design include a control arm?

**CQ-11** Is a station mechanism part kept apart from AICOR's robot-body link?

**CQ-12** Is a well's medium a biological sample contained in the well (not a part)?

**CQ-13** Is a derived robot motion step a robot-scientist body-motion designator (the lowest refinement level)?

**CQ-14** Is the plan derived for an information-gain requirement an experimental protocol, organised in protocol sessions?

**CQ-15** Is a selected experiment a scientific proposal (selection is not warrant, RS ED2)?

**CQ-16** Is the kernel's dispense a substance-manipulation designator at device-command level, not a body motion (action categories aligned with the designator levels)?

**CQ-17** Is the kernel's picking-up a plate-transfer (scene-step) designator of the transport facet, and not a kind of the transporting it is a phase of (specialisation kept apart from partonomy)?

**CQ-18** Does every kernel audit entry record one designator's lifecycle transition?


## NOT answered by the L2 (by design)

- Numeric operating limits of the vendor devices: no vendor manual is in the repository; the contracts carry none (D016: none are invented).

