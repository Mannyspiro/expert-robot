# Merlin optional FreeCAD geometry adapter

`freecad_adapter.py` implements the geometry backend protocol using a caller-supplied FreeCAD Python runtime. It is opt-in: no FreeCAD installation, executable discovery, subprocess, or network access is performed. Construct it with explicit runtime modules, or call `FreeCADBackend.from_freecad_runtime(EXACT_BUILD_VERSION)` from a compatible FreeCAD Python environment.

The adapter imports a STEP/IGES/mesh file into a temporary FreeCAD document, collects per-shape validity, topology counts, bounding boxes and placement matrices, and optionally exports STL meshes and scalar geometry reports. It closes its temporary document after the job. Mesh tessellation accepts explicit `mesh_parameters.linear_deflection` and `mesh_parameters.angular_deflection`; defaults are 0.1 and 0.5 in the units expected by the configured FreeCAD build.

Example host-side use (inside the selected FreeCAD Python runtime):

    backend = FreeCADBackend.from_freecad_runtime("FreeCAD-<exact-build>")
    receipt = execute_job(request, workspace, output_dir, backend)

The host must still call `cad_geometry_backend.execute_job` so input and output hashes, workspace confinement, backend identity and receipt integrity are checked. The job contract now admits the optional `mesh_parameters` object.

Important limitations:
- No FreeCAD runtime is bundled or installed by Merlin; no live FreeCAD execution has been performed as part of this PR.
- STEP/IGES import hierarchy and placement behavior can vary by format and FreeCAD build. The adapter reports object placements but does not yet guarantee reconstruction of the source assembly's semantic parent-child hierarchy.
- Source units and coordinate-frame conversion are not inferred. The request's units/frame must be established by the caller.
- Shape validity is FreeCAD's own check, not independent proof of manufacturability, dimensional correctness, watertightness, or engineering suitability.
- Volume and surface area are sums over imported shapes; overlapping solids may therefore be double-counted.
- STL export is tessellated output, not a lossless CAD representation. Record the exact FreeCAD build and mesh parameters with every run.
- This adapter does not run an MCFC solver, electrical solver, collision detection, mating/joint solver, or independent topology qualification.
