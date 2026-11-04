import unittest
from datetime import datetime, timedelta, timezone

from merlin.cad_assembly import AssemblyComponent, CADAssembly, Transform3D
from merlin.cpu_fabric.leases import CapacitySnapshot, LeaseBook, LeaseError, cad_wire_route_request
from merlin.engineering_ir import EngineeringProject, Net, Part, Pin
from merlin.wire_routing import route_physical_netlist, run_wire_route_with_lease


def project_with_endpoints(*, obstacle=False, missing=False, multi=False):
    pin = lambda number, name: Pin(
        number, name,
        position_mm=None if missing else (0.0, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
    )
    parts = [
        Part("J1", "source connector", (pin("1", "OUT"),), size_mm=(2, 2, 2)),
        Part("J2", "destination connector", (pin("1", "IN"),), size_mm=(2, 2, 2)),
    ]
    components = [
        AssemblyComponent("J1"),
        AssemblyComponent("J2", Transform3D(translation_mm=(30, 0, 0))),
    ]
    endpoints = ["J1.1", "J2.1"]
    if obstacle:
        parts.append(Part("U1", "intervening module", (pin("1", "NC"),),
                          size_mm=(10, 10, 10)))
        components.append(AssemblyComponent("U1", Transform3D(translation_mm=(15, 0, 0))))
    if multi:
        parts.append(Part("J3", "third connector", (pin("1", "IN2"),), size_mm=(2, 2, 2)))
        components.append(AssemblyComponent("J3", Transform3D(translation_mm=(30, 20, 0))))
        endpoints.append("J3.1")
    project = EngineeringProject(
        "wire-route-test", "mm", tuple(parts),
        (Net("SIGNAL", tuple(endpoints), nominal_voltage_v=3.3, max_current_a=0.01),),
    )
    return project, CADAssembly("wire-route-assembly", tuple(components))


class WireRoutingTests(unittest.TestCase):
    def test_clear_pair_gets_deterministic_candidate(self):
        project, assembly = project_with_endpoints()
        first = route_physical_netlist(project, assembly)
        second = route_physical_netlist(project, assembly)
        route = first["nets"][0]["routes"][0]
        self.assertEqual(route["status"], "candidate_geometry_not_manufacturing_qualified")
        self.assertEqual(route["length_mm"], 30.0)
        self.assertEqual(first, second)

    def test_obstacle_forces_overpass_candidate(self):
        project, assembly = project_with_endpoints(obstacle=True)
        result = route_physical_netlist(project, assembly)
        route = result["nets"][0]["routes"][0]
        self.assertEqual(route["status"], "candidate_geometry_not_manufacturing_qualified")
        self.assertEqual(route["method"], "global_z_overpass")
        self.assertGreater(max(point[2] for point in route["polyline_mm"]), 5.0)

    def test_missing_pin_geometry_is_never_guessed(self):
        project, assembly = project_with_endpoints(missing=True)
        result = route_physical_netlist(project, assembly)
        route = result["nets"][0]["routes"][0]
        self.assertEqual(route["status"], "unroutable_missing_endpoint_geometry")
        self.assertIsNone(route["polyline_mm"])

    def test_multi_terminal_net_uses_deterministic_star(self):
        project, assembly = project_with_endpoints(multi=True)
        result = route_physical_netlist(project, assembly)
        routes = result["nets"][0]["routes"]
        self.assertEqual(len(routes), 2)
        self.assertTrue(all(route["from"] == "J1.1" for route in routes))
        for route in routes:
            points = route["polyline_mm"]
            for start, end in zip(points, points[1:]):
                changed_axes = sum(abs(start[i] - end[i]) > 1e-10 for i in range(3))
                self.assertLessEqual(changed_axes, 1)

    def test_route_execution_requires_active_mcfc_lease(self):
        project, assembly = project_with_endpoints()
        now = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)
        capacity = CapacitySnapshot(2, 1024**3, None, None, 50, now.isoformat(),
                                    "synthetic-route-execution", "e" * 64)
        book = LeaseBook(capacity)
        request = cad_wire_route_request(
            "leased-route", estimated_memory_bytes=1024**2,
            max_wall_seconds=10, compute_budget_units=5,
        )
        lease = book.grant(request, now=now, ttl_seconds=10)
        output = run_wire_route_with_lease(
            project, assembly, book, lease.lease_id, now=now
        )
        self.assertEqual(output["execution"]["mcfc_lease_id"], lease.lease_id)
        self.assertFalse(output["execution"]["promotion_authority"])

    def test_expired_mcfc_lease_blocks_route_execution(self):
        project, assembly = project_with_endpoints()
        now = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)
        capacity = CapacitySnapshot(2, 1024**3, None, None, 50, now.isoformat(),
                                    "synthetic-route-execution", "f" * 64)
        book = LeaseBook(capacity)
        request = cad_wire_route_request(
            "expired-route", estimated_memory_bytes=1024**2,
            max_wall_seconds=10, compute_budget_units=5,
        )
        lease = book.grant(request, now=now, ttl_seconds=10)
        with self.assertRaisesRegex(LeaseError, "deadline"):
            run_wire_route_with_lease(
                project, assembly, book, lease.lease_id,
                now=now + timedelta(seconds=11),
            )

    def test_invalid_clearance_rejected(self):
        project, assembly = project_with_endpoints()
        for value in (-1.0, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                route_physical_netlist(project, assembly, clearance_mm=value)

    def test_output_never_claims_manufacturing_approval(self):
        project, assembly = project_with_endpoints()
        result = route_physical_netlist(project, assembly)
        self.assertEqual(result["status"],
                         "GEOMETRY_PROPOSAL_ONLY_NOT_ELECTRICAL_OR_MANUFACTURING_APPROVAL")
        self.assertIn("No conductor gauge", result["limitations"][1])


if __name__ == "__main__":
    unittest.main()
