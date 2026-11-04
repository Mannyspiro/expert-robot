# Authoritative source register and equation crosswalk

**Citation policy:** a source supports only the claims and equation families actually covered by its content. A citation to a broad course or standard is not evidence that every application-specific model has been validated. Uncovered entries remain explicitly marked for primary-source completion.

## Source register

- **S01 — Convex optimization:** MIT OpenCourseWare, *Introduction to Convex Optimization* (6.079, Fall 2009). Covers convex modeling, least squares, linear/quadratic/semidefinite programs, optimality and duality, and scientific/engineering applications. https://ocw.mit.edu/courses/6-079-introduction-to-convex-optimization-fall-2009/
- **S02 — Convex optimization text:** Boyd & Vandenberghe, *Convex Optimization*, Stanford-hosted author resource and examples. https://web.stanford.edu/~boyd/cvxbook/
- **S03 — SI dimensions and units:** NIST, *Guide to the SI*, Chapter 7, dimensions and dimensional exponents. https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-7-rules-and-style-conventions-expressing-values
- **S04 — SI base quantities:** NIST, *The International System of Units (SI), SP 330*, including seven base quantities and derived dimensions. https://www.nist.gov/pml/special-publication-330/sp-330-section-2
- **S05 — Uncertainty propagation:** NIST TN 1297, Appendix A, law of propagation of uncertainty. https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-appendix-law-propagation-uncertainty
- **S06 — Measurement uncertainty:** Possolo, NIST TN 1900, measurement models and uncertainty evaluation. https://doi.org/10.6028/NIST.TN.1900
- **S07 — SymPy dimensional system:** SymPy 1.14 documentation, physical dimensions and unit systems. https://docs.sympy.org/latest/modules/physics/units/dimensions.html
- **S08 — Applied PDEs and numerical methods:** MIT OCW 18.086, *Mathematical Methods for Engineers II*: heat, wave, convection, conservation laws, stability, finite differences, Fourier methods, sparse linear systems, optimization. https://ocw.mit.edu/courses/18-086-mathematical-methods-for-engineers-ii-spring-2006/
- **S09 — NASA state estimation:** NASA Technical Memorandum 2022-0007267, Kalman filter appendix, LTI state-space model, discretization, noise assumptions and covariance updates. https://ntrs.nasa.gov/api/citations/20220007267/downloads/NASA-TM-20220007267.pdf
- **S10 — Sampling and DSP:** IEEE Technology Navigator, digital signal processing and sampling theorem overview. https://technav.ieee.org/area/digital-signal-processing/
- **S11 — Sampling theorem teaching reference:** Carnegie Mellon University, *The Nyquist-Shannon Sampling Theorem*. https://www.cs.cmu.edu/~15322/book/ch07/01.html
- **S12 — Reproducible random streams:** NumPy documentation, Generator and seeded default_rng. https://numpy.org/doc/stable/reference/random/generator.html
- **S13 — Logistic growth:** OpenStax, *Calculus Volume 2*, Section 4.4, logistic equation, carrying capacity, initial-value solution and interpretation. https://openstax.org/books/calculus-volume-2/pages/4-4-the-logistic-equation
- **S14 — Enzyme kinetics context:** OpenStax Biology, Section 6.5, enzyme catalysis and reaction-rate context. https://openstax.org/books/biology/pages/6-5-enzymes
- **S15 — Michaelis–Menten derivation/context:** Chemistry LibreTexts, Michaelis–Menten kinetics and reaction scheme. https://chem.libretexts.org/Bookshelves/Biological_Chemistry/Supplemental_Modules_%28Biological_Chemistry%29/Enzymes/Enzymatic_Kinetics/Michaelis-Menten_Kinetics
- **S16 — Spectral graph theory:** Carnegie Mellon University lecture notes, graph Laplacian, eigenvalues and connectivity. https://www.cs.cmu.edu/~venkatg/teaching/15252-sp21/notes/spectral-GT-spring2020.pdf
- **S17 — Spectral graph theory applications:** Simons Institute / UC Berkeley, spectral graph theory, expanders, eigenvalues and graph partitioning. https://simons.berkeley.edu/spectral-graph-theory
- **S18 — Lean formalization background:** *Mathematics in Lean*, linear algebra, modules, matrices and vector spaces. https://mathlib.org/theories/linear_algebra.html
- **S19 — Post-quantum lattice standard:** NIST FIPS 203, ML-KEM and Module Learning with Errors basis. https://csrc.nist.gov/pubs/fips/203/final
- **S20 — Relativity/geometric equations:** NASA Glenn, field equations and equations of motion (educational introduction; use primary GR texts/papers for technical validation). https://www.grc.nasa.gov/WWW/k-12/Numbers/Math/Mathematical_Thinking/field_equations.htm
- **S21 — Einstein field equation technical reference:** NASA/JPL-hosted technical document on Einstein field equations, metric, energy-momentum and curvature tensors. https://spsweb.fltops.jpl.nasa.gov/portaldataops/mpg/MPG_Docs/Source%20Docs/Einstein%27s%20Field%20Equations.pdf

## Equation-ID crosswalk

| Atlas IDs | Source mapping | Evidence boundary / remaining source work |
|---|---|---|
| 001–010 | S01, S02, S03, S05 | Optimization and estimation foundations supported; add domain-specific references for finance/robust decision applications. |
| 011–020 | S03, S04, S16, S17, S18 | Linear algebra, graph Laplacian and dimensions supported; add primary references for each geometric construction. |
| 021–030 | S03, S09 | State-space and Kalman model supported; PID/LQR/robot dynamics/kinematics need specialist control and robotics references per entry. |
| 031–040 | S03, S08 | Conservation, heat, wave, finite-difference/PDE foundations supported; Maxwell and constitutive relations require EM primary references. |
| 041–050 | S03, S07, S10, S11, S12 | Sampling, transform and dimensional computation foundations supported; entropy/coding/complexity need dedicated sources per entry. |
| 051–060 | S03, S08 | FEM/numerical methods supported at course level; elasticity, fatigue, fracture, buckling and AM process laws need standards/material-specific primary sources. |
| 061–070 | S03, S13, S14, S15 | Logistic growth and enzyme kinetics context supported; SIR, Lotka–Volterra, gene regulation, PK and allometry need dedicated domain sources. |
| 071–080 | S03, S08 | Network linear algebra foundations supported; shortest path, queueing, reliability, inventory and input-output require dedicated OR/engineering references. |
| 081–090 | S03, S05 | Uncertainty and statistical foundations supported; CAPM, VaR, survival and regression require finance/statistics primary references. |
| 091–100 | S03, S18, S19, S20, S21 | Tensor/linear-algebra, lattice standard and introductory relativity references supported; Floquet, geometric algebra and equivariant ML need dedicated references. |

## Status

This is a source-to-entry crosswalk, not a claim that every entry has already received a complete primary-source audit. Entries with explicit gaps must remain UNVERIFIED for application-specific use until a source directly supports the model, assumptions, and regime. The source register should be expanded entry-by-entry before a production promotion.


## Additional sources for RWEA-021–030

- **S22 — Linear systems and feedback control:** MIT OpenCourseWare, 16.30 *Feedback Control Systems*, Fall 2010, lecture notes on state-space models, controllability, state feedback, estimators, LQR, LQG, and digital control. https://ocw.mit.edu/courses/16-30-feedback-control-systems-fall-2010/pages/lecture-notes/
- **S23 — Robot kinematics and rigid-body transformations:** Kevin M. Lynch and Frank C. Park, *Modern Robotics*, Northwestern University/Cambridge University Press online chapter supplements; Chapters 3–6 cover rigid-body motions, product-of-exponentials forward kinematics, Jacobians, singularities, and inverse kinematics. https://modernrobotics.northwestern.edu/nu-gm-book-resource/
- **S24 — Multibody and manipulator dynamics:** Russ Tedrake, MIT, *Underactuated Robotics*, “Multi-Body Dynamics,” Lagrangian equations and manipulator equations. https://underactuated.mit.edu/multibody.html
- **S25 — PID control:** Karl J. Åström and Richard M. Murray, *Feedback Systems*, Caltech, introductory feedback-control text and PID control treatment. https://www.cds.caltech.edu/~murray/books/AM08/pdf/am08-intro_09Aug12.pdf
- **S26 — Manipulator stiffness and impedance control:** Russ Tedrake, MIT, *Robotic Manipulation*, Chapter 8 “Manipulator Control,” including joint stiffness control and generalized manipulator dynamics. https://manipulation.mit.edu/force.html

## Equation-ID crosswalk additions

| Atlas IDs | Source mapping | Evidence boundary / remaining source work |
|---|---|---|
| 021 | S22 | Supports continuous-time state-space modeling; application-specific state/input units and model identification remain to be supplied. |
| 022 | S22, S09 | Supports discrete state-space and estimation context; discretization method and process/measurement noise assumptions must be specified per system. |
| 023 | S09, S22 | Supports Kalman filtering/state estimation; covariance units, noise assumptions, and observability must be checked for each application. |
| 024 | S25, S22 | Supports ideal PID form and feedback context; practical derivative filtering, saturation, anti-windup, and tuning are implementation-specific. |
| 025 | S22 | Supports deterministic LQR formulation; stabilizability/detectability, cost-matrix dimensions, and continuous/discrete convention must be stated. |
| 026 | S23 | Supports product-of-exponentials forward kinematics; robot-specific screw axes, home pose, frame conventions, and joint units are required. |
| 027 | S23 | Supports Jacobian velocity mapping; distinguish body/space Jacobian and mixed revolute/prismatic joint units. |
| 028 | S23 | Supports numerical inverse kinematics; local convergence, singularities, joint limits, and solution selection are application-dependent. |
| 029 | S24, S23 | Supports Lagrangian manipulator dynamics; friction, actuator mapping, contact, constraints, and sign conventions require model-specific treatment. |
| 030 | S26 | Supports joint-space stiffness/PD control; gain units, gravity compensation, actuator limits, and closed-loop stability require robot-specific validation. |


## Additional sources for RWEA-031–040

- **S27 — Partial differential equations:** MIT OpenCourseWare, 18.152 *Introduction to Partial Differential Equations*, Fall 2011. Lecture sequence covers heat, Laplace, Poisson, wave, transport, and related PDE theory. https://ocw.mit.edu/courses/18-152-introduction-to-partial-differential-equations-fall-2011/pages/lecture-notes/
- **S28 — Numerical PDEs and conservation laws:** MIT OpenCourseWare, 18.336 *Numerical Methods for Partial Differential Equations*, Spring 2009. Covers heat, transport, wave, stability, conservation-law theory and numerical methods, and Navier–Stokes discretization. https://ocw.mit.edu/courses/18-336-numerical-methods-for-partial-differential-equations-spring-2009/pages/lecture-notes/
- **S29 — Electromagnetic fields and Maxwell equations:** MIT OpenCourseWare, 6.641 *Electromagnetic Fields, Forces, and Motion*, Spring 2009. Includes integral and differential Maxwell equations, field boundary conditions, and electromagnetic energy/field topics. https://ocw.mit.edu/courses/6-641-electromagnetic-fields-forces-and-motion-spring-2009/resources/lecture-notes/

## Equation-ID crosswalk additions

| Atlas IDs | Source mapping | Evidence boundary / remaining source work |
|---|---|---|
| 031 | S27, S28 | Local conservation balance supported at PDE-course level; flux constitutive law and source terms remain application-specific. |
| 032 | S27, S28 | Heat equation supported; anisotropy, phase change, radiation, and material-property calibration require separate treatment. |
| 033 | S27, S28 | Advection-diffusion family supported; turbulence closures and reaction kinetics need application-specific sources. |
| 034 | S27, S28 | Linear wave equation supported; damping, dispersion, material constitutive laws, and boundary reflections remain model-specific. |
| 035 | S27 | Laplace equation and elliptic theory supported; physical interpretation and boundary uniqueness must be checked per use. |
| 036 | S27 | Poisson equation and Green-function context supported; source sign, gauge, and boundary compatibility require per-domain review. |
| 037 | S27, S28 | Transport/advection family supported; conservative versus nonconservative form depends on variable velocity and physical density. |
| 038 | S28 | Numerical Navier–Stokes methods supported at course level; turbulence closure, rheology, compressibility, and boundary conditions remain unresolved per case. |
| 039 | S29 | MIT notes cover differential Maxwell equations; macroscopic material constitutive relations and interface conditions need separate review. |
| 040 | S29 | Maxwell field framework supports derivation context; Poynting theorem and material-medium energy expressions require a dedicated derivation and sign-convention audit. |


## Additional sources for RWEA-041–050

- **S30 — Fourier representations, filtering, and sampling:** MIT OpenCourseWare, 6.003 *Signals and Systems*, Fall 2011. Lecture notes cover Fourier representations, Fourier series/transforms, convolution, filtering, frequency response, discrete-time representations, and sampling. https://ocw.mit.edu/courses/6-003-signals-and-systems-fall-2011/pages/lecture-notes/
- **S31 — Sampling theorem and reconstruction:** MIT OpenCourseWare, 2.161 *Signal Processing: Continuous and Discrete*, Fall 2008, Lecture 10. The lecture handout develops the band-limited sampling theorem, reconstruction conditions, and discrete Fourier transform. https://ocw.mit.edu/courses/2-161-signal-processing-continuous-and-discrete-fall-2008/2934569026a399e9062597924c730a78_lecture_10.pdf
- **S32 — Entropy, coding, quantization, Fourier and sampling:** MIT OpenCourseWare, 6.450 *Principles of Digital Communication I*, Fall 2009. Lecture notes include Fourier transforms, sampling, entropy, source coding, quantization, random processes, and mutual information-related communication theory. https://ocw.mit.edu/courses/6-450-principles-of-digital-communication-i-fall-2009/pages/lecture-notes/

## Equation-ID crosswalk additions

| Atlas IDs | Source mapping | Evidence boundary / remaining source work |
|---|---|---|
| 041 | S30 | Fourier series representation supported; convergence mode and endpoint conventions require explicit treatment for discontinuous signals. |
| 042 | S30 | Fourier transform and inverse convention supported; normalization and generalized-function assumptions must be stated. |
| 043 | S30 | Convolution and LTI systems supported; zero-state assumptions and impulse normalization must be explicit. |
| 044 | S30 | Frequency response and filtering supported; stability, causality, and realization are separate properties. |
| 045 | S30, S31 | DFT family supported; normalization, periodic extension, leakage, and bin-to-frequency mapping require exact conventions. |
| 046 | S31, S30 | Band-limited sampling theorem supported; ideal assumptions differ from practical anti-alias filters and finite precision systems. |
| 047 | S32 | Quantization topics supported; Δ²/12 is only the ideal uniform-error model under stated assumptions, not a universal converter-noise law. |
| 048 | S32 | Discrete source entropy supported; log base determines units and finite-sample estimation bias is not addressed by the formula. |
| 049 | S32 | Information-theory source materials support the topic; joint-distribution identities and finite-sample estimators need separate reproducible checks. |
| 050 | S30, S32 | Spectral analysis and random-process material support the topic; PSD normalization, stationarity, ergodicity, and one-/two-sided conventions need explicit audit. |
