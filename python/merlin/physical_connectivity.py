"""Map typed electrical net endpoints onto resolved 3D assembly pin locations."""
from __future__ import annotations

from typing import Any

from merlin.cad_assembly import CADAssembly, Transform3D, validate_assembly
from merlin.coordinate_frames import compose, resolve_frames, transform_point
from merlin.engineering_ir import EngineeringProject, validate_project


def transform_vector(transform: Transform3D, vector: tuple[float, float, float]):
    """Rotate a direction vector without applying translation."""
    r = transform.rotation
    return tuple(
        sum(r[row * 3 + col] * vector[col] for col in range(3))
        for row in range(3)
    )


def physical_netlist(project: EngineeringProject, assembly: CADAssembly) -> dict[str, Any]:
    """Return net endpoints with world pin coordinates where supplied.

    Pin coordinates and directions are local to the part's geometric center.
    Part.position_mm is a further local offset inside its assembly component.
    """
    errors = [issue for issue in validate_project(project) if issue.severity == "error"]
    errors.extend(issue for issue in validate_assembly(project, assembly)
                  if issue.severity == "error")
    if errors:
        raise ValueError("cannot map physical netlist: " +
                         "; ".join(issue.code for issue in errors))

    parts = {part.ref: part for part in project.parts}
    components = {item.part_ref: item for item in assembly.components}
    frame_world = resolve_frames(assembly.frames)
    endpoint_map: dict[str, dict[str, Any]] = {}

    for part_ref, component in components.items():
        part = parts[part_ref]
        world = component.transform
        if component.frame_id is not None:
            world = compose(frame_world[component.frame_id], world)
        world = compose(world, Transform3D(translation_mm=part.position_mm))
        for pin in part.pins:
            endpoint = part_ref + "." + pin.number
            if pin.position_mm is None:
                endpoint_map[endpoint] = {
                    "part_ref": part_ref, "pin_number": pin.number,
                    "position_mm": None, "direction": None,
                    "status": "missing_physical_pin_geometry",
                }
                continue
            position = transform_point(world, pin.position_mm)
            direction = (None if pin.direction is None
                         else transform_vector(world, pin.direction))
            endpoint_map[endpoint] = {
                "part_ref": part_ref, "pin_number": pin.number,
                "position_mm": list(position),
                "direction": None if direction is None else list(direction),
                "status": "located" if direction is not None else "position_only",
            }

    nets = []
    for net in sorted(project.nets, key=lambda item: item.name):
        endpoints = []
        for endpoint in sorted(net.endpoints):
            record = endpoint_map.get(endpoint)
            if record is None:
                endpoints.append({"endpoint": endpoint, "position_mm": None,
                                  "status": "not_in_assembly"})
            else:
                endpoints.append({"endpoint": endpoint, **record})
        nets.append({
            "name": net.name,
            "net_class": net.net_class,
            "nominal_voltage_v": net.nominal_voltage_v,
            "max_current_a": net.max_current_a,
            "endpoints": endpoints,
            "route_geometry_status": "not_generated",
        })

    return {
        "format": "merlin-physical-netlist-v1",
        "units": "mm",
        "project": project.name,
        "assembly": assembly.name,
        "nets": nets,
        "limitations": [
            "Pin coordinates are user-supplied local geometry, not inferred from a datasheet.",
            "No wire path, gauge, clearance, impedance, thermal or manufacturability analysis is performed.",
            "Missing pin geometry is reported explicitly; it is never guessed.",
        ],
    }
