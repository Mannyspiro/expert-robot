# Math Kung Fu — lesson sequence generated from the atlas

Lessons are generated only from claims whose mathematical structure and assumptions are stated. A lesson's evidence label follows its strongest verified layer; a visualization is an aid, not proof.

## Lesson 001 — Optimization is a shape problem
**Model:** fixed-area rectangle, minimize perimeter.  
**Equation:** A=xy, P=2x+2y.  
**Intuition:** if one side gets longer, the other must shrink; the unbalanced rectangle pays a perimeter penalty.  
**Formal core:** (x+y)² ≥ 4xy, with equality when x=y.  
**Recall:** why does balance minimize the perimeter at fixed area?  
**Extension:** derive the result for fixed area A.

## Lesson 002 — Units are the grammar of physics
**Model:** velocity v = distance/time.  
**Dimensions:** [v]=L T⁻¹.  
**Intuition:** equations must compare quantities of the same kind.  
**Recall:** can a length be added to a temperature? Why not?  
**Extension:** derive the dimensions of force, energy, pressure, and power.

## Lesson 003 — Heat is local averaging
**Model:** ∂T/∂t = α∇²T.  
**Units:** [α]=L²/T.  
**Intuition:** a hot point loses heat to cooler neighbours; the Laplacian measures local curvature.  
**Recall:** why does a flat temperature profile have zero diffusion term?  
**Extension:** compare continuous diffusion with the discrete grid update and stability parameter.

## Lesson 004 — A signal has two coordinate stories
**Model:** Fourier transform and sampling.  
**Intuition:** the same signal can be represented over time or as a mixture of frequencies. Sampling too slowly makes different high-frequency signals indistinguishable.  
**Recall:** why does sampling below twice the maximum frequency permit aliasing?  
**Extension:** build two distinct sinusoids that produce the same samples.

## Lesson 005 — Growth meets a ceiling
**Model:** dN/dt = rN(1−N/K).  
**Units:** [r]=T⁻¹; [N]=[K]=population.  
**Intuition:** growth is fast when resources are abundant and slows near carrying capacity.  
**Recall:** what are the two equilibrium populations?  
**Extension:** compare exponential and logistic growth and identify when each assumption is plausible.

## Lesson 006 — A system can be observed, not directly seen
**Model:** state-space plus Kalman filtering.  
**Intuition:** hidden state evolves; sensors provide noisy partial views.  
**Recall:** why does a filter need both a process model and an observation model?  
**Extension:** represent one robot pose in world, body, and sensor frames.

## Lesson 007 — Networks have geometry too
**Model:** graph Laplacian L=D−A.  
**Intuition:** the Laplacian measures how unlike a node is from its neighbours.  
**Recall:** why does a constant value on every node produce zero graph diffusion?  
**Extension:** compare graph eigenvectors with vibration modes of a physical structure.

## Lesson 008 — A model is a map, not the territory
**Model:** XMG multi-frame representation.  
**Intuition:** one object can have physical, state-space, graph, and spectral descriptions.  
**Recall:** what is the difference between changing coordinates and changing the object?  
**Extension:** track which projections lose information.

## Teaching protocol
For each lesson: 1) one short visual, 2) one concrete physical example, 3) one equation, 4) one transformation between representations, 5) one recall question, 6) one small experiment, 7) one evidence/assumption note. Introduce no more than two new mathematical ideas at once in beginner lessons.
