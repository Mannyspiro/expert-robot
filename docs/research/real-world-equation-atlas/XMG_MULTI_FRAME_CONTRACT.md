# XMG multi-frame contract for the equation atlas

## 1. Shared mathematical object

Represent one underlying state or object as

`X = (O, F, M, T, I, P)`

- `O`: canonical object/state, independent of display notation.
- `F`: typed frames (physical, material, sensor, graph, spectral, state-space, spacetime).
- `M`: metric or measurement structure where defined.
- `T`: typed maps between frames.
- `I`: invariants and their domains of validity.
- `P`: provenance, assumptions, units, and information-loss metadata.

## 2. Frame types

| Frame | Example | Coordinate meaning |
|---|---|---|
| Cartesian physical | (x,y,z) in metres | position in a declared Euclidean reference frame |
| Material/Lagrangian | (X,Y,Z) | labels material points in a reference configuration |
| Sensor/body | SE(3) pose | location/orientation relative to a sensor or robot body |
| State-space | x(t) in R^n | selected dynamical state variables, not necessarily physical spatial axes |
| Graph | vertex index / adjacency | discrete relational state |
| Spectral | Fourier coefficients / eigenbasis | representation in frequency or operator modes |
| Spacetime | (ct,x,y,z) with metric signature declared | relativistic event coordinates |
| Higher-dimensional embedding | coordinates in R^n, n>3 | mathematical embedding; extra coordinates are not automatically physical dimensions |

## 3. Transformation semantics

Every map must declare one of:
- **Passive coordinate change:** same physical object, new coordinates; invertible on declared domain.
- **Active transformation:** physical/geometric operation on the object.
- **Projection:** maps to fewer degrees of freedom; generally information-losing.
- **Embedding:** injects an object into a larger representation space; preserve source identity and distinguish embedding coordinates from measured physical dimensions.
- **Measurement/observation:** maps state to sensor output; may be noisy and non-invertible.
- **Basis change:** changes component representation while preserving the represented linear object.

Store domain, codomain, units, invertibility/injectivity, Jacobian where relevant, and loss metadata.

## 4. Invariants

Candidate invariants must be tied to a transformation group and assumptions:
- Euclidean rigid motion: pairwise distances and angles.
- Proper rotations: orientation and determinant +1.
- Linear basis change: rank and eigenvalues under similarity transforms.
- Graph relabeling: spectrum and connectivity.
- Fourier transform: total energy under the stated normalization (Parseval).
- Conservation PDE: integral balance with boundary flux/source terms.
- Relativity: spacetime interval under Lorentz transformations.
- Numerical solver: declared conserved quantity/residual within stated tolerance, not exact unless proved.

Do not label an arbitrary coordinate value as invariant.

## 5. Example: garden optimization object

Canonical object: rectangular region with area 12 m².
- Physical frame: side lengths (x,y) in metres.
- Constraint frame: scalar area xy in m².
- Objective frame: perimeter 2x+2y in metres.
- Dimensionless frame: normalized ratios x/sqrt(A), y/sqrt(A).
- Invariant: area under the constrained family; perimeter is the optimized observable, not an invariant.
- Map: (x,y) -> (xy, 2x+2y), with explicit unit conversion and domain x,y>0.

## 6. Example: one-dimensional heat field

Canonical field: T(x,t), with x in metres, t in seconds, T in kelvin.
- Physical frame: sampled temperature field T_i(t).
- Grid frame: indices i plus spacing Δx in metres.
- Spectral frame: discrete Fourier coefficients of the spatial profile.
- State-space frame: vector [T_1,...,T_n]ᵀ.
- Operator frame: discrete Laplacian matrix.
- Invariants/diagnostics: boundary conditions, discrete energy decay for source-free diffusion, solver stability parameter αΔt/Δx².
- Projection from continuous field to grid is discretization; record mesh and information loss.

## 7. Visualization contract

Each visual should show:
1. One canonical object.
2. Two or more explicitly named frames.
3. Arrows for maps, labelled with map type.
4. Units and axis conventions.
5. At least one invariant and one non-invariant.
6. Lossy projections with a visible information-loss cue.
7. Evidence status and numerical tolerance.

No unlabeled extra dimensions, arbitrary axis mixing, or implication that a visualization proves a physical theory.
