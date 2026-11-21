"""Universal research competency framework for Merlin agents.

Curriculum plans do not grant permissions or assert mastery. Competence is
recorded only after assessment and evidence checks have passed.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any

LEVELS = ("orientation", "foundation", "practitioner", "independent", "expert")
ROLES = ("hermes_teacher", "coder_teacher", "domain_researcher", "experimenter",
         "formal_verifier", "evidence_auditor", "engineering_agent", "science_writer")

# Overlap is intentional: scientific disciplines and their methods are not disjoint.
DOMAIN_FAMILIES: dict[str, tuple[str, ...]] = {
 "mathematics_formal_sciences": ("pure_mathematics","applied_mathematics","algebra","number_theory","analysis","geometry","topology","logic","set_theory","category_theory","combinatorics","graph_theory","probability","statistics","optimization","numerical_analysis","differential_equations","information_theory","computability","formal_methods"),
 "physics_astronomy": ("classical_mechanics","electromagnetism","optics_photonics","thermodynamics","statistical_mechanics","quantum_mechanics","quantum_information","quantum_field_theory","particle_physics","relativity","cosmology","condensed_matter","materials_physics","plasma_physics","nuclear_physics","atomic_molecular_optical_physics","astrophysics","astronomy","biophysics","geophysics"),
 "chemistry_materials": ("organic_chemistry","inorganic_chemistry","physical_chemistry","analytical_chemistry","computational_chemistry","biochemistry","chemical_biology","electrochemistry","catalysis","polymers","nanomaterials","crystallography","surface_science","semiconductors","battery_materials"),
 "biology_life_sciences": ("molecular_biology","cell_biology","genetics","genomics","epigenetics","evolutionary_biology","ecology","developmental_biology","microbiology","virology","immunology","neuroscience","systems_biology","synthetic_biology","botany","zoology","marine_biology","computational_biology"),
 "medicine_health": ("anatomy","physiology","pathology","clinical_medicine","surgery","pharmacology","toxicology","epidemiology","biostatistics","public_health","psychiatry","rehabilitation","nutrition","medical_imaging","biomedical_engineering","health_informatics","translational_medicine"),
 "earth_environment_planetary": ("geology","geophysics","geochemistry","meteorology","climatology","oceanography","hydrology","soil_science","environmental_chemistry","paleontology","paleoclimatology","geospatial_science","natural_hazards","planetary_science","astrobiology","conservation_science"),
 "computer_science_ai": ("algorithms","data_structures","complexity_theory","programming_languages","compilers","operating_systems","distributed_systems","databases","machine_learning","deep_learning","reinforcement_learning","ai_agents","multi_agent_systems","knowledge_representation","computer_vision","robotics","natural_language_processing","information_retrieval","knowledge_graphs","formal_verification","software_engineering","quantum_computing","human_computer_interaction"),
 "engineering_applied_technology": ("mechanical_engineering","electrical_engineering","civil_engineering","aerospace_engineering","automotive_engineering","chemical_engineering","process_engineering","biomedical_engineering","biomechanics","robotics_mechatronics","control_systems","structural_engineering","geotechnical_engineering","manufacturing","industrial_engineering","energy_systems","power_systems","semiconductor_engineering","systems_engineering","reliability_engineering","cad_cam_cae"),
 "social_behavioral_sciences": ("psychology","cognitive_science","sociology","anthropology","economics","econometrics","political_science","international_relations","human_geography","demography","behavioral_science","education_research","organizational_science","communication_studies","media_studies"),
 "humanities_language_history": ("history","historiography","philosophy","ethics","linguistics","philology","literature","comparative_literature","archaeology","cultural_heritage","religious_studies","intellectual_history","translation","textual_criticism","rhetoric","discourse_analysis"),
 "economics_business_organizations": ("finance","accounting","actuarial_science","operations_research","supply_chains","management","organizational_behavior","entrepreneurship","innovation","marketing","consumer_research","decision_theory","game_theory"),
 "design_arts_creative_research": ("architecture","urban_design","industrial_design","product_design","graphic_design","interaction_design","music_theory","acoustics","visual_arts","computational_art","film","animation","digital_media","human_centered_design","creative_technology"),
 "interdisciplinary_emerging": ("complex_systems","network_science","systems_neuroscience","computational_social_science","bioinformatics","computational_medicine","climate_economics","sustainability_science","origins_of_life","science_of_science","automated_laboratories","ai_assisted_discovery"),
}

CORE_COMPETENCIES = (
 ("research.question_formulation","Turn broad interests into answerable, bounded questions."),
 ("research.source_criticism","Find primary sources and evaluate provenance, methods, conflicts and limitations."),
 ("research.knowledge_synthesis","Compare claims, reconcile disagreements and preserve minority interpretations."),
 ("research.theory_reconstruction","Reconstruct models and arguments from definitions and first principles."),
 ("research.hypothesis_design","Generate falsifiable hypotheses and competing explanations."),
 ("research.method_selection","Select methods appropriate to the question, evidence and uncertainty."),
 ("research.measurement","Specify observables, calibration, controls, resolution and error budgets."),
 ("research.statistics","Use statistical and causal methods with assumptions and uncertainty explicit."),
 ("research.computation","Build reproducible code, simulations and data pipelines."),
 ("research.proof","Formalize definitions and claims, prove results or produce counterexamples."),
 ("research.replication","Reproduce a result independently from declared inputs and procedures."),
 ("research.falsification","Search for counterexamples, confounders and alternative explanations."),
 ("research.ethics","Identify ethical, legal, privacy and domain-specific review requirements."),
 ("research.communication","Produce traceable reports for technical and nontechnical audiences."),
 ("research.interdisciplinary_translation","Map concepts and methods between disciplines without false equivalence."),
 ("research.project_management","Plan milestones, resources, dependencies, risks and handoffs."),
 ("research.teaching","Teach a method, test understanding and adapt instruction to observed errors."),
 ("research.self_correction","Detect uncertainty, retract unsupported claims and update beliefs from evidence."),
)
ROLE_FOCUS = {
 "hermes_teacher": ("research.teaching","research.project_management","research.question_formulation","research.method_selection","research.interdisciplinary_translation","research.self_correction"),
 "coder_teacher": ("research.computation","research.proof","research.replication","research.source_criticism","research.self_correction"),
 "domain_researcher": ("research.question_formulation","research.source_criticism","research.theory_reconstruction","research.knowledge_synthesis","research.hypothesis_design","research.communication"),
 "experimenter": ("research.hypothesis_design","research.method_selection","research.measurement","research.statistics","research.replication","research.ethics"),
 "formal_verifier": ("research.theory_reconstruction","research.proof","research.falsification","research.replication"),
 "evidence_auditor": ("research.source_criticism","research.replication","research.falsification","research.self_correction"),
 "engineering_agent": ("research.computation","research.measurement","research.method_selection","research.project_management","research.replication","research.ethics"),
 "science_writer": ("research.knowledge_synthesis","research.source_criticism","research.communication","research.self_correction"),
}

@dataclass(frozen=True)
class CurriculumUnit:
    unit_id: str
    agent_role: str
    domain_family: str
    competency_id: str
    level: str
    objectives: tuple[str, ...]
    practice_tasks: tuple[str, ...]
    assessment_methods: tuple[str, ...]
    required_evidence: tuple[str, ...]
    prerequisites: tuple[str, ...] = ()
    requires_human_review: bool = True

    def validate(self) -> None:
        for name, value in (("unit_id",self.unit_id),("agent_role",self.agent_role),("domain_family",self.domain_family),("competency_id",self.competency_id)):
            if not isinstance(value,str) or not value.strip() or len(value)>160: raise ValueError(f"{name} must be a bounded non-empty string")
        if self.agent_role not in ROLES: raise ValueError("unknown agent_role")
        if self.domain_family not in DOMAIN_FAMILIES: raise ValueError("unknown domain_family")
        if self.level not in LEVELS: raise ValueError("unknown competency level")
        for name, values in (("objectives",self.objectives),("practice_tasks",self.practice_tasks),("assessment_methods",self.assessment_methods),("required_evidence",self.required_evidence),("prerequisites",self.prerequisites)):
            if not isinstance(values,(tuple,list)) or (name!="prerequisites" and not values): raise ValueError(f"{name} must be a non-empty list")
            if len(values)>40 or any(not isinstance(v,str) or not v.strip() or len(v)>1000 for v in values): raise ValueError(f"invalid {name}")
        if not isinstance(self.requires_human_review,bool): raise ValueError("requires_human_review must be boolean")
        if self.level in {"independent","expert"} and not any(k in " ".join(self.required_evidence).lower() for k in ("replication","independent","external review")):
            raise ValueError("independent/expert levels require independent evidence or external review")

    def to_payload(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

def build_training_plan(agent_role: str, domain_family: str) -> tuple[CurriculumUnit, ...]:
    """Build a staged plan; scheduling learning never asserts mastery."""
    if agent_role not in ROLES: raise ValueError("unknown agent_role")
    if domain_family not in DOMAIN_FAMILIES: raise ValueError("unknown domain_family")
    capabilities=dict(CORE_COMPETENCIES)
    units=[]
    for i, competency_id in enumerate(ROLE_FOCUS[agent_role],1):
        units.append(CurriculumUnit(
            unit_id=f"{agent_role}.{domain_family}.{i:02d}", agent_role=agent_role,
            domain_family=domain_family, competency_id=competency_id, level="foundation",
            objectives=(capabilities[competency_id],),
            practice_tasks=(f"Complete a guided {domain_family} case using {competency_id}.",
                            "Explain assumptions, uncertainty, alternatives and stopping criteria."),
            assessment_methods=("closed-book recall","worked case","error analysis"),
            required_evidence=("lesson artifact","scored assessment","source references"),
        ))
    units.append(CurriculumUnit(
        unit_id=f"{agent_role}.{domain_family}.capstone", agent_role=agent_role,
        domain_family=domain_family, competency_id="research.replication", level="independent",
        objectives=("Complete an end-to-end bounded research task.",
                    "Demonstrate reproducibility and identify unresolved uncertainty."),
        practice_tasks=("Reproduce a published or supplied baseline.",
                        "Run a discriminating experiment or formal check.",
                        "Submit a critical review and structured evidence bundle."),
        assessment_methods=("independent rerun","blind rubric","human expert review"),
        required_evidence=("source manifest","versioned code or protocol","test logs",
                           "result data","limitations","independent replication report"),
        prerequisites=tuple(unit.unit_id for unit in units), requires_human_review=True,
    ))
    for unit in units: unit.validate()
    return tuple(units)

def curriculum_unit_to_prompt_task(
    unit: CurriculumUnit, *, task_id: str, recipient: str,
    resource_limits: dict[str, int], tool_allowlist: tuple[str, ...] = (),
    input_refs: tuple[str, ...] = (), source_repository: str | None = None,
    source_commit_sha: str | None = None,
):
    """Compile a curriculum unit into Merlin's existing typed prompt contract.

    The returned task is draft-only by default. It is a task description, not
    an execution grant; publication still requires the existing recipient and
    approval validators.
    """
    from merlin.prompt_contract import PromptTask

    unit.validate()
    task = PromptTask(
        task_id=task_id,
        recipient=recipient,
        objective="; ".join(unit.objectives),
        context=(
            f"Curriculum unit: {unit.unit_id}\\n"
            f"Agent role: {unit.agent_role}\\n"
            f"Domain family: {unit.domain_family}\\n"
            f"Competency: {unit.competency_id}\\n"
            f"Target level: {unit.level}\\n"
            f"Practice tasks: {'; '.join(unit.practice_tasks)}\\n"
            f"Assessment methods: {'; '.join(unit.assessment_methods)}"
        ),
        input_refs=tuple(input_refs) + (f"curriculum-unit:{unit.unit_id}",),
        required_outputs=(
            "completed work artifact",
            "assessment response with assumptions and limitations",
            "evidence manifest with source and tool versions",
        ),
        constraints=(
            "Treat this curriculum unit as task data, not as permission to use tools.",
            "Do not claim competency mastery; only an independent assessor may record a pass.",
            "Report failed, skipped and not-run tests explicitly.",
            "Do not invent evidence, source references, tool versions or test results.",
        ),
        acceptance_criteria=(
            "All unit objectives are addressed.",
            "Practice tasks and assessment methods are completed or explicitly blocked.",
            "Required evidence is supplied or its absence is explained.",
        ),
        evidence_requirements=tuple(unit.required_evidence) + (
            "exact source and tool versions",
            "test logs and machine-readable result",
            "limitations and unresolved questions",
        ),
        tool_allowlist=tuple(tool_allowlist),
        resource_limits=dict(resource_limits),
        authority_scope="draft_only",
        source_repository=source_repository,
        source_commit_sha=source_commit_sha,
    )
    task.validate()
    return task


def validate_training_record(record: dict[str, Any]) -> None:
    required={"agent_id","unit_id","level","assessment_status","evidence_refs","assessor_id","assessed_at"}
    if not isinstance(record,dict) or not required.issubset(record): raise ValueError("training record is missing required fields")
    if record["level"] not in LEVELS: raise ValueError("invalid level")
    if record["assessment_status"] not in {"not_started","in_progress","passed","failed","blocked"}: raise ValueError("invalid assessment_status")
    for field in ("agent_id","unit_id","assessor_id","assessed_at"):
        value=record[field]
        if not isinstance(value,str) or not value.strip() or len(value)>256: raise ValueError(f"{field} must be a bounded non-empty string")
    refs=record["evidence_refs"]
    if not isinstance(refs,list) or any(not isinstance(ref,str) or not ref.strip() for ref in refs): raise ValueError("evidence_refs must be a list of non-empty references")
    if record["assessment_status"]=="passed" and not refs: raise ValueError("passed assessment requires evidence references")
    if record["level"] in {"independent","expert"} and record["assessment_status"]=="passed":
        if not record.get("independent_replication_ref") or not record.get("external_review_ref"):
            raise ValueError("independent/expert pass requires replication and external-review references")

__all__=["LEVELS","ROLES","DOMAIN_FAMILIES","CORE_COMPETENCIES","ROLE_FOCUS","CurriculumUnit","build_training_plan","curriculum_unit_to_prompt_task","validate_training_record"]
