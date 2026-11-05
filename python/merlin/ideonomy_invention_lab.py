"""Ideonomy-based fictional-technology translation into testable engineering concepts.

The catalogue abstracts cinematic tropes into functions; it does not copy
protected designs or assume fictional physics is real. Scores are transparent
triage heuristics, never proof of novelty or feasibility.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping

from merlin.knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry


@dataclass(frozen=True)
class ResearchSource:
    source_id: str
    title: str
    url: str
    evidence_note: str


@dataclass(frozen=True)
class InventionCandidate:
    candidate_id: str
    name: str
    cinematic_function: str
    real_world_translation: str
    subsystem_combination: tuple[str, ...]
    prototype: str
    cad_scope: tuple[str, ...]
    electrical_scope: tuple[str, ...]
    simulation_plan: tuple[str, ...]
    maturity: str
    evidence: tuple[str, ...]
    unknowns: tuple[str, ...]
    scores: Mapping[str, float]

    @property
    def weighted_score(self) -> float:
        weights = {
            "feasibility": 0.25, "testability": 0.20,
            "evidence": 0.20, "safety": 0.15,
            "integration": 0.10, "novelty_hypothesis": 0.10,
        }
        return round(sum(self.scores[k] * w for k, w in weights.items()), 2)

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "weighted_score": self.weighted_score}


SOURCES = (
    ResearchSource(
        "nature-neuromorphic-2025",
        "Neuromorphic computing at scale",
        "https://www.nature.com/articles/s41586-024-08253-8",
        "Review of scalable brain-inspired compute architectures and their ecosystem challenges.",
    ),
    ResearchSource(
        "nature-photonic-reservoir-2026",
        "Scalable photonic reservoir computing for parallel machine learning tasks",
        "https://www.nature.com/articles/s41467-025-67983-z",
        "Experimental photonic reservoir-computing platform; promising research result, not a drop-in CPU replacement.",
    ),
    ResearchSource(
        "nasa-lasar-2026",
        "Ground Demonstration of Autonomous Robotic Laser Beam Welding for In-Space Servicing, Assembly, and Manufacturing",
        "https://ntrs.nasa.gov/citations/20260007230",
        "Ground demonstration integrating robot motion planning, perception, welding and additive deposition.",
    ),
    ResearchSource(
        "nasa-assemblers",
        "Advancing Commercial Space: Autonomous Systems and Robotics",
        "https://technology.nasa.gov/advancing-commercial-space/autonomous_systems_robotics",
        "NASA technology portfolio describes modular autonomous assemblers and automated additive manufacturing.",
    ),
    ResearchSource(
        "nature-artificial-muscle-2025",
        "Ultrasound-driven programmable artificial muscles",
        "https://www.nature.com/articles/s41586-025-09650-3",
        "Research demonstration of ultrasound-addressed microbubble arrays producing programmable deformation.",
    ),
    ResearchSource(
        "nature-photonic-ai-2025",
        "Integrated photonic neuromorphic computing for AI acceleration",
        "https://advanced.onlinelibrary.wiley.com/doi/10.1002/adma.202508029",
        "Review of photonic neural devices, architectures and integration challenges.",
    ),
)


def seed_candidates() -> tuple[InventionCandidate, ...]:
    """Curated first-wave hypotheses, each with an explicit real-world test path."""
    return (
        InventionCandidate(
            "titan-adaptive-compute-loom",
            "Titan Adaptive Compute Loom",
            "A ship computer that distributes work across specialized subsystems.",
            "A software-first, CPU-based compute fabric with a typed task graph, locality-aware scheduling, vectorized kernels, telemetry and optional accelerator adapters. Photonics and neuromorphic hardware remain future plug-in research paths.",
            ("Merlin Hermes task graph", "CPU SIMD/vector kernels", "memory-local work queues",
             "event-driven telemetry", "CACE verified artifact receipts"),
            "A two-node low-voltage bench fabric that runs the same bounded numerical workload locally and across nodes, measuring throughput, joules per task, latency and recovery.",
            ("two modular compute trays", "airflow duct and fan mounts",
             "DIN/rail power distribution plate", "cable combs", "serviceable front panel"),
            ("certified external 12 V DC adapter", "fused 12 V input",
             "regulated 5 V compute rails", "12 V fan branch",
             "Ethernet switch and node links", "temperature and current telemetry"),
            ("RK4 numerical workload", "queue latency and throughput benchmark",
             "thermal step-response model", "power-per-completed-task comparison"),
            "software prototype feasible; accelerator fabric exploratory",
            ("nature-neuromorphic-2025", "nature-photonic-reservoir-2026",
             "nature-photonic-ai-2025"),
            ("CPU SIMD is not equivalent to a GPU; benchmark actual kernels",
             "power and cooling budgets depend on selected boards",
             "photonic/neuromorphic modules need independent hardware validation"),
            {"feasibility": 8.5, "testability": 9.5, "evidence": 8.0,
             "safety": 9.0, "integration": 8.0, "novelty_hypothesis": 6.5},
        ),
        InventionCandidate(
            "modular-autonomous-fabricator",
            "Modular Autonomous Fabricator Cell",
            "A replicator or robotic workshop that assembles objects from digital plans.",
            "A bounded tabletop cell combining additive manufacturing, a small pick-and-place arm, machine vision, fiducial registration and post-build inspection. It fabricates only materials and processes supported by the selected hardware.",
            ("FreeCAD parametric parts", "robot motion planning", "camera-based registration",
             "toolhead interchange", "CACE geometry and receipt checks"),
            "A guarded, low-force desktop cell that prints a fixture, locates it with a camera, and performs a repeatable pick/place or probe operation.",
            ("extrusion-frame enclosure", "toolhead carriage", "camera bracket",
             "swappable end-effector plate", "fixture and calibration grid"),
            ("24 V certified external supply", "fused low-voltage motor branches",
             "stepper drivers", "limit switches", "camera USB", "emergency stop input"),
            ("kinematic reachability", "collision envelope", "toolpath time estimate",
             "repeatability and placement-error measurement"),
            "component technologies demonstrated; integrated cell requires prototyping",
            ("nasa-lasar-2026", "nasa-assemblers"),
            ("process-specific guarding and interlocks required",
             "printer and arm integration needs calibrated coordinate frames",
             "not a general-purpose molecular replicator"),
            {"feasibility": 7.0, "testability": 9.0, "evidence": 8.5,
             "safety": 7.0, "integration": 7.0, "novelty_hypothesis": 7.0},
        ),
        InventionCandidate(
            "soft-tendon-assist",
            "Soft-Tendon Assist Sleeve",
            "A lightweight powered suit that augments movement.",
            "A non-wearable bench demonstrator using compliant textile routing, Bowden cables, load cells and a current-limited motor spool to study assist timing. Human-worn use is explicitly out of scope until mechanical, electrical and clinical safety work is completed.",
            ("compliant textile structure", "tendon transmission", "force sensing",
             "closed-loop motor control", "biomechanical model"),
            "A single-joint instrumented test rig that moves a dummy linkage against known loads and logs force, travel, temperature and current.",
            ("hinged test fixture", "cable guides", "motor spool bracket",
             "load-cell mount", "mechanical travel stops"),
            ("isolated low-voltage motor supply", "current-limited driver",
             "load-cell amplifier", "encoder", "hardware stop circuit"),
            ("torque-speed envelope", "cable friction and hysteresis",
             "control stability", "thermal duty cycle"),
            "bench prototype plausible; wearable performance unproven",
            ("nature-artificial-muscle-2025",),
            ("artificial-muscle paper is a research-scale mechanism, not a ready actuator",
             "human biomechanics and injury limits need expert review",
             "no powered human-worn prototype in this phase"),
            {"feasibility": 6.5, "testability": 8.5, "evidence": 7.0,
             "safety": 6.5, "integration": 6.5, "novelty_hypothesis": 7.5},
        ),
        InventionCandidate(
            "spatial-engineering-table",
            "Spatial Engineering Table",
            "A holodeck-like room that makes digital systems tangible.",
            "A spatial digital-twin workstation combining a 3D scene graph, CAD assemblies, tracked input and multi-view display or AR. The near-term version is a monitor/AR-assisted interactive model, not a free-space hologram.",
            ("XMG coordinate transforms", "FreeCAD assembly graph", "tracked input",
             "real-time scene renderer", "simulation overlays"),
            "A desk-scale digital twin that synchronizes a CAD assembly, electrical net graph and simulation plots under one coordinate and provenance model.",
            ("modular display/marker frame", "camera mounts", "adjustable sensor rail",
             "calibration targets"),
            ("USB-C display and sensor links", "low-voltage sensor hub",
             "optional LED illumination", "network connection"),
            ("coordinate-frame calibration", "latency and registration error",
             "occlusion and display readability"),
            "software prototype feasible; immersive display varies by hardware",
            ("nature-photonic-ai-2025",),
            ("a spatial overlay is not a volumetric hologram",
             "tracking accuracy and display ergonomics require measurement"),
            {"feasibility": 8.0, "testability": 9.0, "evidence": 7.0,
             "safety": 9.0, "integration": 8.0, "novelty_hypothesis": 6.5},
        ),
        InventionCandidate(
            "field-sense-tricorder",
            "Field-Sense Multimodal Surveyor",
            "A handheld tricorder that rapidly characterizes its surroundings.",
            "A modular environmental and materials survey instrument combining temperature, humidity, pressure, visible/IR imaging and selected gas or particulate sensors. It reports measurements and uncertainty, not medical diagnoses or unsupported material identification.",
            ("sensor fusion", "calibration metadata", "uncertainty propagation",
             "edge signal processing", "replaceable sensor cartridges"),
            "A benchtop sensor puck with three calibrated sensors, timestamped acquisition and a dashboard that compares readings against reference instruments.",
            ("handheld enclosure", "sensor cartridge rails", "airflow inlet",
             "optical window", "battery compartment"),
            ("protected low-voltage battery pack", "regulated sensor rails",
             "I2C/SPI sensor bus", "USB data", "battery monitor"),
            ("sensor calibration curves", "noise and drift analysis",
             "cross-sensor agreement", "environmental response time"),
            "sensor fusion prototype feasible; each sensing claim needs calibration",
            ("nature-neuromorphic-2025",),
            ("no universal sensor detects arbitrary substances",
             "gas sensors have selectivity and cross-sensitivity limits",
             "no medical or life-safety certification"),
            {"feasibility": 8.0, "testability": 9.0, "evidence": 7.0,
             "safety": 8.0, "integration": 8.0, "novelty_hypothesis": 6.0},
        ),
    )


def build_ideonomy_report() -> dict[str, Any]:
    candidates = sorted(seed_candidates(), key=lambda item: (-item.weighted_score, item.candidate_id))
    return {
        "schema": "merlin-ideonomy-invention-report/1",
        "method": {
            "name": "FIND-N / Ideonomy functional decomposition and simplex recombination",
            "steps": [
                "abstract fictional devices into user-visible functions",
                "decompose functions into physical, computational and information primitives",
                "map each primitive to publicly documented real technologies",
                "recombine across domains while preserving physical constraints",
                "score feasibility, testability, evidence, safety, integration and novelty hypothesis",
                "define a falsifiable prototype and measurable outputs",
                "record assumptions, unknowns and evidence provenance",
            ],
            "score_notice": "Heuristic triage only; not a patentability, novelty, safety or performance certification.",
        },
        "titan_context": {
            "role": "CPU-first heterogeneous compute fabric orchestrated by Merlin Hermes and governed by CACE-MCFC",
            "principle": "Capability grows, authority never expands.",
            "boundary": "No GPU-equivalence claim; no unverified photonic or neuromorphic hardware assumed.",
        },
        "sources": [asdict(source) for source in SOURCES],
        "candidates": [candidate.as_dict() for candidate in candidates],
    }


def register_ideonomy_report(
    *, registry: MerlinRegistry, graph: MerlinKnowledgeGraph,
    project_id: str, logical_path: str = "research/ideonomy/future-tech-v1.json",
) -> dict[str, Any]:
    """Persist the reproducible report and graph its concepts to the Titan module."""
    report = build_ideonomy_report()
    encoded = (json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    digest = registry.put_artifact(project_id, logical_path, encoded,
                                   "application/vnd.merlin.ideonomy-report+json")
    if not registry.verify_artifact(digest):
        raise RuntimeError("Ideonomy report failed canonical artifact verification")
    artifact_id = "artifact:" + digest[:32]
    graph.add_node(GraphNode(
        artifact_id, "artifact", "Merlin Ideonomy future-technology report",
        {"sha256": digest, "project_id": project_id, "logical_path": logical_path,
         "schema": report["schema"]},
        evidence_class="unreviewed", source_uri="registry://sha256/" + digest,
    ))
    titan_id = "module:titan-adaptive-compute-loom"
    graph.add_node(GraphNode(
        titan_id, "module", "Titan Adaptive Compute Loom",
        {"role": report["titan_context"]["role"],
         "principle": report["titan_context"]["principle"],
         "report_sha256": digest},
        evidence_class="unreviewed", source_uri="registry://sha256/" + digest,
    ))
    graph.add_edge(GraphEdge(titan_id, "uses", artifact_id, {"report_sha256": digest}))
    for candidate in report["candidates"]:
        node_id = "model:ideonomy-" + candidate["candidate_id"]
        graph.add_node(GraphNode(
            node_id, "model", candidate["name"],
            {"candidate": candidate, "report_sha256": digest},
            evidence_class="unreviewed", source_uri="registry://sha256/" + digest,
        ))
        graph.add_edge(GraphEdge(node_id, "derived_from", artifact_id,
                                 {"method": report["method"]["name"]}))
        if candidate["candidate_id"] == "titan-adaptive-compute-loom":
            graph.add_edge(GraphEdge(titan_id, "implements", node_id,
                                     {"relationship": "candidate architecture"}))
    return {"schema": "merlin-ideonomy-registration/1", "artifact_sha256": digest,
            "artifact_verified": True, "artifact_node_id": artifact_id,
            "titan_node_id": titan_id, "candidate_count": len(report["candidates"]),
            "candidate_node_ids": ["model:ideonomy-" + c["candidate_id"] for c in report["candidates"]]}


__all__ = ["ResearchSource", "InventionCandidate", "seed_candidates",
           "build_ideonomy_report", "register_ideonomy_report", "SOURCES"]
