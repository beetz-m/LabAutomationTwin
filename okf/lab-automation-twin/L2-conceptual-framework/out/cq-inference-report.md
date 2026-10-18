# Competency-question inference report

  [ANSWERED ] CQ-1 — Is Cell 01's automated incubator an AICOR lab-automation device and an incubation device?
             AutomatedCO2Incubator ⊑ IncubationDevice
  [ANSWERED ] CQ-2 — Is a device manual's operating procedure an AICOR / robot-scientist action contract?
             OperatingProcedure ⊑ ActionContract
  [ANSWERED ] CQ-3 — Is a device failure mode an AICOR failure signature, recovered by a repair?
             DeviceFailureMode ⊑ hasRecoveryProcedure some RecoveryProcedure
  [ANSWERED ] CQ-4 — Is a recovery procedure an AICOR Repair?
             RecoveryProcedure ⊑ Repair
  [ANSWERED ] CQ-5 — Is a lab safety rule a universal prohibition (AICOR IncapabilityAssertion, a BodyWorldConstraint)?
             LabSafetyRule ⊑ BodyWorldConstraint
  [ANSWERED ] CQ-6 — Is a biosafety rule a contamination-compatibility gate on interventions?
             BiosafetyRule ⊑ ContaminationCompatibility
  [ANSWERED ] CQ-7 — Is an authorisation rule a norm rather than a causal safety prohibition?
             AuthorizationNorm ⊑ Norm, and not a IncapabilityAssertion
  [ANSWERED ] CQ-8 — Can an SDT node be the physical thing it represents?
             LabSDTNode and LabArtifact are disjoint — no individual is both (via AbstractEntity ⟂ PhysicalEntity)
  [ANSWERED ] CQ-9 — Is a culture experiment run an AICOR manipulation episode?
             CultureExperimentRun ⊑ ManipulationEpisode
  [ANSWERED ] CQ-10 — Does the challenge-rescue design include a control arm?
             ChallengeRescueStudyDesign ⊑ hasArm some ControlArm
  [ANSWERED ] CQ-11 — Is a station mechanism part kept apart from AICOR's robot-body link?
             MechanismPart ⊑ dul_PhysicalObject, and not a Link
  [ANSWERED ] CQ-12 — Is a well's medium a biological sample contained in the well (not a part)?
             CultureMediumPortion ⊑ isContainedIn some Well
  [ANSWERED ] CQ-13 — Is a derived robot motion step a robot-scientist body-motion designator (the lowest refinement level)?
             PlaceMotion ⊑ BodyMotionDesignator
  [ANSWERED ] CQ-14 — Is the plan derived for an information-gain requirement an experimental protocol, organised in protocol sessions?
             ExperimentRealisationPlan ⊑ hasSession some ProtocolSession
  [ANSWERED ] CQ-15 — Is a selected experiment a scientific proposal (selection is not warrant, RS ED2)?
             SelectedExperiment ⊑ ScientificProposal, and not a ScientificConclusion
  [ANSWERED ] CQ-16 — Is the kernel's dispense a substance-manipulation designator at device-command level, not a body motion (action categories aligned with the designator levels)?
             DispenseCommand ⊑ SubstanceManipulationDesignator, and not a MotionStepDesignator
  [ANSWERED ] CQ-17 — Is the kernel's picking-up a plate-transfer (scene-step) designator of the transport facet, and not a kind of the transporting it is a phase of (specialisation kept apart from partonomy)?
             PickingUpDesignator ⊑ TransportFacetDesignator, and not a TransportingDesignator
  [ANSWERED ] CQ-18 — Does every kernel audit entry record one designator's lifecycle transition?
             CommitmentAuditEntry ⊑ hasTransition some DesignatorLifecycleState

cq: PASS — all 18 competency question(s) answered by inference over the reasoned ontology · in step with the prose.
