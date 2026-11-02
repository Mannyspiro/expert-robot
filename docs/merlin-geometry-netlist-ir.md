# Merlin geometry and wiring intermediate representations

This increment adds a small, typed foundation for engineering drafts. It is deliberately a validation/export layer, not a finished CAD system or electrical design authority.

## Geometry IR

The geometry module defines point IDs, 3D coordinates, faces, units and a closed-solid flag. It checks:
- finite coordinates and unique point identifiers;
- supported units (mm, cm, m, in);
- face references, duplicate/degenerate faces and zero-area surfaces;
- manifold edge use, including exactly two incident faces for closed solids;
- unit conversion and bounding boxes.

Valid polygon meshes can be exported as OpenSCAD polyhedron source. This lets a generative image or sketch workflow propose geometry, then convert accepted dimensions/topology into a typed artifact. The renderer is not a verifier: downstream CAD kernels and manufacturing checks are still required.

## Wiring/netlist IR

The netlist module defines components, pins, pin roles, nets and declared voltage/current values. It checks:
- duplicate component/net identifiers;
- unknown components and pins;
- pins assigned to multiple nets;
- simple supply-to-ground shorts;
- declared net voltage/current against component ratings.

These checks are only structural preflight. They are not circuit simulation, PCB DRC, electrical safety certification, code compliance, or permission to energize hardware. A qualified engineer must review every real design.

## Problem reframing rule

A geometry failure can sometimes be reframed as a graph/topology constraint problem; a wiring failure can be reframed as a graph connectivity/rating constraint problem. The mapping must preserve vertex/pin identity, incidence, units, boundary conditions and component limits. If it does not, reject the analogy rather than accepting a convenient but incorrect solution.

## Tests

Run:

    python3 -m unittest discover -s tests/engineering -v

All candidate geometry and netlist records remain unqualified until domain-specific CAD/electrical validation is added.
