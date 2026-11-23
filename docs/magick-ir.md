# Magick IR v0.1 — Historical Rituals as Experimental Protocols

## Purpose

This research layer treats historical ritual instructions as structured, testable protocols without presuming either supernatural truth or fraud.

The system separates:

- textual/symbolic information,
- exact geometry and topology,
- acoustics,
- materials,
- orientation,
- timing,
- environment,
- human action,
- known-physics prediction,
- measured residuals,
- historical provenance,
- and evidence level.

Historical claims are never promoted to physical truth by repetition or manuscript count.

## Core representation

A ritual is modeled as:

```
R = (G, S, M, A, O, T, E, H, Y, C)
```

where:

- G = geometry/topology
- S = symbols/glyphs/names
- M = materials
- A = acoustics
- O = orientation
- T = timing/sequence
- E = environmental conditions
- H = human actions/state
- Y = measured observables
- C = claimed outcome

The JSON Schema lives at:

`config/schemas/magick_experiment.schema.json`

## CACE mapping

The intended CACE execution chain is:

```
historical witness
-> exact geometric reconstruction
-> mesh / coordinate functions
-> material + boundary-condition assignment
-> sparse operator
-> solver
-> residual
-> a-posteriori error estimator
-> interval / certified bound
-> adaptive refinement
-> evidence certificate
```

For an observation y and known-physics prediction F(theta):

```
r = y - F(theta)
```

A candidate anomaly may only exist if the measured residual exceeds the certified numerical + instrument + environmental uncertainty envelope.

```
||r|| > eta_numeric + eta_instrument + eta_environment
```

A solver result alone is not evidence of unknown physics.

## Exact geometry bridge

Expert Robot already provides a Lean exact-geometry kernel for rational:

- Point3
- Vec3
- Line3
- Plane3
- Sphere3
- dot/cross products
- orthogonality
- parallelism
- point-on-line/plane/sphere predicates

Future Magick IR compilation should lower manuscript diagrams into those exact primitives first, then into approximate meshes only when needed.

## Spoken language is dual representation

An invocation is represented simultaneously as:

1. symbolic/informational content;
2. a physical waveform.

The waveform layer may carry:

- fundamental frequency,
- harmonic spectrum,
- SPL,
- phase,
- rhythm,
- repetitions,
- spatial position,
- live-vs-recorded provenance.

This allows controlled separation of semantic content from acoustic physics.

Recommended ablation family:

```
A = original words + original waveform
B = altered words + matched spectral structure
C = original words + altered spectral structure
D = recorded original
E = silence
```

The goal is to identify which channel, if any, carries predictive information.

## Portal hypothesis classes

Use the word "portal" only as a hypothesis class.

- P0_perceptual — altered perception/vision/local display
- P1_information — anomalous information transfer
- P2_field_energy — anomalous localized field or energy coupling
- P3_matter_transport — nonlocal transport of matter
- P4_spacetime_connection — traversable connection between spacetime regions

Current historical texts are richer in claims of manifestation, vision, communication, containment, and presence than in literal human traversal.

No P3 or P4 claim currently has reproducible physical evidence.

## Historical source families

Initial retrospective compilation target:

1. Liber Iuratus / Sworn Book of Honorius
2. Hygromanteia / Magical Treatise of Solomon
3. Heptameron
4. Clavicula / Key of Solomon traditions
5. Later Lemegeton descendants where useful for transmission analysis

Useful source anchors:

- British Library Royal MS 17 A XLII: Liber iuratus Honorii
  https://searcharchives.bl.uk/catalog/041-003419951
- Hedegard, Liber Iuratus Honorii: A Critical Edition (2002)
- Hygromanteia / Magical Treatise of Solomon, water-divination section
- Heptameron circle instructions
- British Library Sloane Clavicula/Lemegeton manuscript catalogue records

The Hygromanteia water-divination operation is especially useful experimentally because it combines geometry, water, silver, vine wood, a magnet, vocal recitation, optics/perception, and a specific sequence.

## Witness-conditioned transmission

Copied instructions are not independent experimental observations.

For each feature locus l and witness w, use a transmission-aware weight:

```
W(w,l) =
  provenance_confidence
  * independence_weight
  * legibility
  * locus_uniqueness
```

Multiple visual mutations from one source diagram should be capped as one effective locus when they are not independent.

High-information transmission characters:

- exact topology,
- ring count,
- fixed name order,
- angular positions,
- openings/boundary breaks,
- exact ratios/distances,
- glyph mutations,
- shared scribal errors,
- unusual materials,
- operation sequence,
- relation between operator and entity locus.

Low-information characters:

- generic circles,
- generic cardinal directions,
- generic protective language,
- common stars/pentagrams without transmission-specific detail.

### Current carried-forward circle state

The current Harley -> Sloane result remains a diagram-family transmission claim, not whole-manuscript descent.

- visual support currently carried forward: 0.95422
- disputed Sloane f.120r/f.120v metadata remains unresolved
- unavailable Sloane f.120r pixels are latent and must not be reconstructed
- Harley f.56r remains exclusion/partition evidence only
- visual and textual channels remain separate
- shared-error/glyph extraction continues as an independent-locus search

These manuscript scores affect historical reconstruction only. They do not count as physical evidence for ritual effects.

## Expert Robot research loop

Map the existing research engine to ritual experiments as follows:

```
historical claim
-> exact formalization proposal
-> complementary hypothesis lenses
-> skeptic gate
-> <= 3 expensive candidates
-> controlled experiment / simulation
-> residual analysis
-> replication
-> evidence ledger
```

Useful existing lenses:

- exact geometric reframing
- spectral/operator reframing
- minimal toy-model reduction
- boundary/extremal probing
- topological obstruction search
- counterfactual assumption analysis
- explicit witness construction
- analogy transfer

The proposer never certifies its own hypothesis.

## Experiment ranking

Reuse the existing generation-budget principle:

```
utility =
  expected_information_gain
  + expected_capability_gain
  - normalized_cost
  - diminishing_returns
```

For this research line, prioritize information gain over spectacle.

Ranked initial queue:

1. Geometry-only null tests
   - rotate, mirror, rescale, perturb topology
   - measure whether any alleged effect tracks exact geometry

2. Acoustic semantic-vs-waveform tests
   - original, spectral controls, recordings, silence

3. Material substitution
   - silver vs matched conductive substitute
   - magnet vs demagnetized sham
   - water vs dielectric/control liquids where safe

4. Orientation tests
   - manuscript-relative, true north, magnetic north, randomized azimuth

5. Human-observer removal
   - camera/sensors only vs observer present

6. Full factorial interaction search
   - only after single-channel effects survive correction and holdout

P3/P4 portal experiments are not promoted merely because lower-level experiments are interesting.

## Evidence promotion ladder

```
UNTESTED
-> ORDINARY / INCONCLUSIVE
-> ANOMALOUS_CANDIDATE
-> REPLICATED_ANOMALY
-> NEW_PHYSICS_CANDIDATE
```

Promotion requires:

- preregistered observable,
- calibrated instruments,
- blinded/randomized controls,
- multiple-testing correction,
- known-physics model,
- numerical error bound,
- holdout success,
- independent replication.

No manuscript claim, AI confidence score, simulation output, or single laboratory anomaly can skip levels.

## First target: Hygromanteia P0/P1 bench

Compile the water-divination operation into Magick IR.

Initial physical channels:

- geometry
- static magnetic field
- conductive silver
- dielectric fluid
- optical reflections/refractions
- live speech acoustics
- human perception

Initial prediction:

Most measurable effects should be explainable by ordinary optics, acoustics, magnetostatics, environmental noise, and observer psychology.

Research value comes from whether any preregistered residual survives those explanations, not from reproducing the historical narrative.

## Next implementation milestones

1. Add a schema validator smoke test.
2. Add one fully typed Hygromanteia example.
3. Add a Magick IR -> exact geometry compiler stub.
4. Add witness-weighted source feature records.
5. Add ablation-plan generation using Expert Robot's research engine.
6. Add CACE adapter contract for mesh/operator/residual/certificate exchange.
7. Keep all evidence fail-closed.
