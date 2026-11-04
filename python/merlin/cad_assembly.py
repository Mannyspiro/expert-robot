"""3D CAD assembly transforms and conservative AABB interference checks."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from typing import Any

from merlin.engineering_ir import EngineeringProject, validate_project

IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)

@dataclass(frozen=True)
class Transform3D:
    rotation: tuple[float, ...] = IDENTITY
    translation_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)

@dataclass(frozen=True)
class AssemblyComponent:
    part_ref: str
    transform: Transform3D = Transform3D()
    frame_id: str | None = None

@dataclass(frozen=True)
class CADAssembly:
    name: str
    components: tuple[AssemblyComponent, ...]
    tolerance_mm: float = 0.01
    frames: tuple[Any, ...] = ()

@dataclass(frozen=True)
class AssemblyIssue:
    code: str
    severity: str
    message: str

def _det(r: tuple[float, ...]) -> float:
    a,b,c,d,e,f,g,h,i = r
    return a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g)

def validate_transform(transform: Transform3D, tolerance: float = 1e-6) -> tuple[str, ...]:
    errors = []
    r = transform.rotation
    if len(r) != 9 or any(not math.isfinite(x) for x in r):
        return ("rotation must contain nine finite values",)
    if len(transform.translation_mm) != 3 or any(not math.isfinite(x) for x in transform.translation_mm):
        errors.append("translation must contain three finite values")
    for row in range(3):
        for col in range(3):
            dot = sum(r[row*3+k] * r[col*3+k] for k in range(3))
            expected = 1.0 if row == col else 0.0
            if abs(dot - expected) > tolerance:
                errors.append("rotation matrix must be orthonormal")
                break
        if errors and errors[-1] == "rotation matrix must be orthonormal":
            break
    if abs(_det(r) - 1.0) > tolerance:
        errors.append("rotation matrix must have determinant +1")
    return tuple(dict.fromkeys(errors))

def _world_aabb(size: tuple[float, float, float], transform: Transform3D):
    half = tuple(value / 2.0 for value in size)
    r = transform.rotation
    extents = tuple(sum(abs(r[row*3+col]) * half[col] for col in range(3))
                    for row in range(3))
    center = transform.translation_mm
    return tuple(center[i] - extents[i] for i in range(3)), tuple(
        center[i] + extents[i] for i in range(3))

def _overlap(a, b, tolerance: float) -> bool:
    amin, amax = a
    bmin, bmax = b
    return all(min(amax[i], bmax[i]) - max(amin[i], bmin[i]) > tolerance
               for i in range(3))

def validate_assembly(project: EngineeringProject, assembly: CADAssembly) -> tuple[AssemblyIssue, ...]:
    from merlin.coordinate_frames import CoordinateFrame, compose, resolve_frames

    issues = [AssemblyIssue(issue.code, issue.severity, issue.message)
              for issue in validate_project(project)]
    parts = {part.ref: part for part in project.parts}
    refs = [component.part_ref for component in assembly.components]
    if len(refs) != len(set(refs)):
        issues.append(AssemblyIssue("DUPLICATE_ASSEMBLY_COMPONENT", "error",
                                    "A part may appear only once in this assembly version."))
    if not math.isfinite(assembly.tolerance_mm) or assembly.tolerance_mm < 0:
        issues.append(AssemblyIssue("INVALID_ASSEMBLY_TOLERANCE", "error",
                                    "Assembly tolerance must be finite and non-negative."))
    try:
        if any(not isinstance(frame, CoordinateFrame) for frame in assembly.frames):
            raise ValueError("frames must contain CoordinateFrame objects")
        frame_world = resolve_frames(assembly.frames)
    except ValueError as exc:
        issues.append(AssemblyIssue("INVALID_FRAME_GRAPH", "error", str(exc)))
        frame_world = {}
    boxes = []
    for component in assembly.components:
        part = parts.get(component.part_ref)
        if part is None:
            issues.append(AssemblyIssue("UNKNOWN_ASSEMBLY_PART", "error",
                                        "Assembly references unknown part " + component.part_ref))
            continue
        errors = list(validate_transform(component.transform))
        if component.frame_id is not None and component.frame_id not in frame_world:
            errors.append("unknown coordinate frame: " + component.frame_id)
        for error in errors:
            issues.append(AssemblyIssue("INVALID_TRANSFORM", "error",
                                        component.part_ref + ": " + error))
        if not errors and all(math.isfinite(x) and x > 0 for x in part.size_mm):
            world = component.transform
            if component.frame_id is not None:
                world = compose(frame_world[component.frame_id], world)
            local_part_offset = Transform3D(translation_mm=part.position_mm)
            world = compose(world, local_part_offset)
            boxes.append((component.part_ref, _world_aabb(part.size_mm, world)))
    if math.isfinite(assembly.tolerance_mm) and assembly.tolerance_mm >= 0:
        for index, (ref_a, box_a) in enumerate(boxes):
            for ref_b, box_b in boxes[index+1:]:
                if _overlap(box_a, box_b, assembly.tolerance_mm):
                    issues.append(AssemblyIssue("AABB_INTERFERENCE", "warning",
                        ref_a + " and " + ref_b + " have overlapping conservative world AABBs."))
    return tuple(issues)

def export_assembly_openscad(project: EngineeringProject, assembly: CADAssembly) -> str:
    from merlin.coordinate_frames import compose, resolve_frames

    issues = validate_assembly(project, assembly)
    if any(issue.severity == "error" for issue in issues):
        raise ValueError("cannot export an invalid CAD assembly")
    parts = {part.ref: part for part in project.parts}
    frame_world = resolve_frames(assembly.frames)
    lines = ["// Generated by Merlin CAD Assembly v1",
             "// AABB checks are conservative and are not exact solid collision tests.",
             "$fn = 48;"]
    for component in sorted(assembly.components, key=lambda item: item.part_ref):
        part = parts[component.part_ref]
        world = component.transform
        if component.frame_id is not None:
            world = compose(frame_world[component.frame_id], world)
        world = compose(world, Transform3D(translation_mm=part.position_mm))
        r = world.rotation
        x, y, z = world.translation_mm
        matrix = [
            [r[0], r[1], r[2], x],
            [r[3], r[4], r[5], y],
            [r[6], r[7], r[8], z],
            [0, 0, 0, 1],
        ]
        lines.append("multmatrix(" + json.dumps(matrix, separators=(",", ":")) + ") {")
        lines.append("  cube(" + json.dumps(list(part.size_mm)) + ", center=true); // " + part.ref)
        lines.append("}")
    return "\n".join(lines) + "\n"

def assembly_report(project: EngineeringProject, assembly: CADAssembly) -> dict[str, Any]:
    issues = validate_assembly(project, assembly)
    return {
        "format": "merlin-cad-assembly-v1",
        "assembly": assembly.name,
        "units": "mm",
        "frames": [{"frame_id": frame.frame_id, "parent_id": frame.parent_id,
                    "rotation": list(frame.transform.rotation),
                    "translation_mm": list(frame.transform.translation_mm)}
                   for frame in sorted(assembly.frames, key=lambda frame: frame.frame_id)],
        "components": [
            {"part_ref": item.part_ref, "rotation": list(item.transform.rotation),
             "translation_mm": list(item.transform.translation_mm), "frame_id": item.frame_id}
            for item in sorted(assembly.components, key=lambda item: item.part_ref)
        ],
        "issues": [asdict(issue) for issue in issues],
        "checks_are_certification": False,
    }