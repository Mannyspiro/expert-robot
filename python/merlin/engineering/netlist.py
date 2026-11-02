"""Structural electrical-netlist IR and conservative consistency checks.

This is a topology/rating preflight only, not circuit simulation, PCB DRC,
electrical safety certification, or authorization to build/energize hardware.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Component:
    id: str
    pins: tuple[str, ...]
    pin_roles: tuple[tuple[str, str], ...] = ()
    max_voltage_v: float | None = None
    max_current_a: float | None = None


@dataclass(frozen=True)
class Connection:
    component: str
    pin: str


@dataclass(frozen=True)
class Net:
    id: str
    connections: tuple[Connection, ...]
    voltage_v: float | None = None
    current_a: float | None = None


@dataclass(frozen=True)
class Netlist:
    components: tuple[Component, ...]
    nets: tuple[Net, ...]


@dataclass(frozen=True)
class NetlistIssue:
    code: str
    message: str


def validate_netlist(netlist: Netlist) -> list[NetlistIssue]:
    issues: list[NetlistIssue] = []
    component_ids = [c.id for c in netlist.components]
    net_ids = [n.id for n in netlist.nets]
    if len(component_ids) != len(set(component_ids)):
        issues.append(NetlistIssue("component.duplicate_id", "Component identifiers must be unique."))
    if len(net_ids) != len(set(net_ids)):
        issues.append(NetlistIssue("net.duplicate_id", "Net identifiers must be unique."))

    components = {c.id: c for c in netlist.components}
    assigned_pins: dict[tuple[str, str], str] = {}
    for net in netlist.nets:
        if len(net.connections) < 2:
            issues.append(NetlistIssue("net.unconnected", f"Net {net.id} must connect at least two pins."))
        roles: set[str] = set()
        for connection in net.connections:
            component = components.get(connection.component)
            if component is None:
                issues.append(NetlistIssue("connection.unknown_component", f"Net {net.id} references missing component {connection.component}."))
                continue
            if connection.pin not in component.pins:
                issues.append(NetlistIssue("connection.unknown_pin", f"Net {net.id} references missing pin {connection.component}.{connection.pin}."))
                continue
            pin_key = (connection.component, connection.pin)
            previous = assigned_pins.get(pin_key)
            if previous is not None and previous != net.id:
                issues.append(NetlistIssue("pin.multiple_nets", f"Pin {connection.component}.{connection.pin} is assigned to nets {previous} and {net.id}."))
            assigned_pins[pin_key] = net.id
            role_map = dict(component.pin_roles)
            role = role_map.get(connection.pin)
            if role:
                roles.add(role.lower())

            if net.voltage_v is not None and component.max_voltage_v is not None:
                if abs(net.voltage_v) > component.max_voltage_v:
                    issues.append(NetlistIssue("rating.voltage_exceeded", f"Net {net.id} exceeds {connection.component} voltage rating."))
            if net.current_a is not None and component.max_current_a is not None:
                if abs(net.current_a) > component.max_current_a:
                    issues.append(NetlistIssue("rating.current_exceeded", f"Net {net.id} exceeds {connection.component} current rating."))

        if "supply" in roles and "ground" in roles:
            issues.append(NetlistIssue("net.supply_ground_short", f"Net {net.id} joins supply and ground pins."))

    return issues
