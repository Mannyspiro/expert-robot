import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from merlin.cad_assembly import AssemblyComponent, CADAssembly, Transform3D
from merlin.cpu_fabric.leases import CapacitySnapshot, LeaseBook, cad_wire_route_request
from merlin.engineering_ir import EngineeringProject, Net, Part, Pin
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.route_evidence import (
    create_route_evidence_receipt, record_route_evidence, verify_route_evidence_receipt,
)
from merlin.wire_routing import route_physical_netlist


def fixture():
    project = EngineeringProject(
        "receipt-project", "mm",
        (
            Part("J1", "source", (Pin("1", "OUT", position_mm=(0, 0, 0)),),
                 size_mm=(2, 2, 2)),
            Part("J2", "target", (Pin("1", "IN", position_mm=(0, 0, 0)),),
                 size_mm=(2, 2, 2)),
            Part("U1", "obstacle", (Pin("1", "NC"),), size_mm=(10, 10, 10)),
        ),
        (Net("N1", ("J1.1", "J2.1"), nominal_voltage_v=3.3, max_current_a=0.01),),
    )
    assembly = CADAssembly(
        "receipt-assembly",
        (
            AssemblyComponent("J1"),
            AssemblyComponent("J2", Transform3D(translation_mm=(30, 0, 0))),
            AssemblyComponent("U1", Transform3D(translation_mm=(15, 0, 0))),
        ),
    )
    now = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)
    capacity = CapacitySnapshot(
        cpu_cores=4, memory_bytes=2 * 1024**3, gpu_count=None,
        gpu_memory_bytes=None, compute_budget_units=100,
        observed_at=now.isoformat(), source="synthetic-route-test-capacity",
        evidence_sha256="c" * 64,
    )
    book = LeaseBook(capacity)
    request = cad_wire_route_request(
        "route-job-001", estimated_memory_bytes=64 * 1024**2,
        max_wall_seconds=30, compute_budget_units=10,
    )
    lease = book.grant(request, now=now, ttl_seconds=30)
    if not book.validate_start(lease.lease_id, now=now):
        raise AssertionError("synthetic MCFC lease should authorize route start")
    output = route_physical_netlist(project, assembly)
    lease = book.complete(lease.lease_id, now=now)
    return project, assembly, output, lease


class RouteEvidenceTests(unittest.TestCase):
    def test_receipt_binds_project_assembly_frames_route_and_mcfc_lease(self):
        project, assembly, output, lease = fixture()
        receipt = create_route_evidence_receipt(
            project, assembly, output, lease, code_revision="a" * 40
        )
        self.assertTrue(verify_route_evidence_receipt(
            receipt, project, assembly, output, lease
        ))
        self.assertEqual(len(receipt["mcfc_lease_sha256"]), 64)
        self.assertEqual(receipt["mcfc_lease"]["capacity_evidence_sha256"], lease.capacity_evidence_sha256)
        self.assertEqual(receipt["mcfc_lease"]["status"], "completed")
        self.assertFalse(receipt["promotion_authority"])
        self.assertEqual(receipt["qualification_status"], "not_qualified")

    def test_tampered_route_output_is_rejected(self):
        project, assembly, output, lease = fixture()
        receipt = create_route_evidence_receipt(
            project, assembly, output, lease, code_revision="a" * 40
        )
        changed = dict(output)
        changed["clearance_assumption_mm"] = 999
        self.assertFalse(verify_route_evidence_receipt(
            receipt, project, assembly, changed, lease
        ))

    def test_changed_assembly_frame_invalidates_receipt(self):
        project, assembly, output, lease = fixture()
        receipt = create_route_evidence_receipt(
            project, assembly, output, lease, code_revision="a" * 40
        )
        moved = CADAssembly(
            assembly.name,
            (assembly.components[0], assembly.components[1],
             AssemblyComponent("U1", Transform3D(translation_mm=(15, 1, 0)))),
            frames=assembly.frames,
        )
        self.assertFalse(verify_route_evidence_receipt(
            receipt, project, moved, output, lease
        ))

    def test_changed_or_elevated_lease_invalidates_receipt(self):
        project, assembly, output, lease = fixture()
        receipt = create_route_evidence_receipt(
            project, assembly, output, lease, code_revision="a" * 40
        )
        elevated = replace(lease, promotion_authority=True)
        self.assertFalse(verify_route_evidence_receipt(
            receipt, project, assembly, output, elevated
        ))
        with self.assertRaisesRegex(ValueError, "completed"):
            create_route_evidence_receipt(
                project, assembly, output, replace(lease, status="active"),
                code_revision="a" * 40,
            )

    def test_receipt_rejects_top_level_authority_expansion(self):
        project, assembly, output, lease = fixture()
        receipt = create_route_evidence_receipt(
            project, assembly, output, lease, code_revision="a" * 40
        )
        elevated = dict(receipt)
        elevated["promotion_authority"] = True
        self.assertFalse(verify_route_evidence_receipt(
            elevated, project, assembly, output, lease
        ))
        with self.assertRaisesRegex(ValueError, "promotion authority"):
            with tempfile.TemporaryDirectory() as tmp:
                ledger = HypothesisLedger(Path(tmp) / "ledger.sqlite3")
                ledger.create("CAD-WIRE-1", "Route geometry is acceptable.")
                record_route_evidence(
                    ledger, "CAD-WIRE-1", elevated, project, assembly, output, lease
                )

    def test_cace_ledger_ingest_does_not_promote_hypothesis(self):
        project, assembly, output, lease = fixture()
        receipt = create_route_evidence_receipt(
            project, assembly, output, lease, code_revision="a" * 40
        )
        with tempfile.TemporaryDirectory() as tmp:
            ledger = HypothesisLedger(Path(tmp) / "ledger.sqlite3")
            ledger.create("CAD-WIRE-1", "The proposed route meets geometric requirements.")
            evidence = record_route_evidence(
                ledger, "CAD-WIRE-1", receipt, project, assembly, output, lease,
                source_url="https://github.com/Mannyspiro/expert-robot/actions/runs/41847081879",
            )
            self.assertEqual(evidence.kind, "experiment")
            self.assertEqual(evidence.artifact_hash, receipt["receipt_sha256"])
            self.assertEqual(ledger.get("CAD-WIRE-1").status, "proposed")

    def test_invalid_source_revision_rejected(self):
        project, assembly, output, lease = fixture()
        with self.assertRaisesRegex(ValueError, "Git SHA"):
            create_route_evidence_receipt(
                project, assembly, output, lease, code_revision="main"
            )


if __name__ == "__main__":
    unittest.main()
