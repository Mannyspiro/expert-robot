import unittest

from merlin.research_curriculum import (
    DOMAIN_FAMILIES, ROLES, CurriculumUnit, build_training_plan,
    curriculum_unit_to_prompt_task, validate_training_record,
)
from merlin.prompt_contract import PromptCompiler


class UniversalResearchCurriculumTests(unittest.TestCase):
    def test_taxonomy_covers_all_registered_roles_and_domains(self):
        self.assertGreaterEqual(len(DOMAIN_FAMILIES), 12)
        self.assertGreaterEqual(sum(len(v) for v in DOMAIN_FAMILIES.values()), 150)
        for role in ROLES:
            for domain in DOMAIN_FAMILIES:
                plan = build_training_plan(role, domain)
                self.assertGreaterEqual(len(plan), 2)
                for unit in plan:
                    unit.validate()

    def test_coder_teacher_has_software_research_competencies(self):
        plan = build_training_plan("coder_teacher", "computer_science_ai")
        ids = {unit.competency_id for unit in plan}
        self.assertIn("research.computation", ids)
        self.assertIn("research.proof", ids)
        self.assertIn("research.replication", ids)

    def test_hermes_teacher_has_pedagogy_and_orchestration_competencies(self):
        plan = build_training_plan("hermes_teacher", "interdisciplinary_emerging")
        ids = {unit.competency_id for unit in plan}
        self.assertIn("research.teaching", ids)
        self.assertIn("research.project_management", ids)
        self.assertIn("research.interdisciplinary_translation", ids)

    def test_curriculum_unit_compiles_to_existing_merlin_prompt_contract(self):
        unit = build_training_plan("coder_teacher", "computer_science_ai")[0]
        task = curriculum_unit_to_prompt_task(
            unit, task_id="curriculum-coder-001", recipient="hermes.research",
            resource_limits={"cpu_cores": 1, "memory_bytes": 268435456,
                             "max_wall_seconds": 90, "compute_budget_units": 50},
            tool_allowlist=("read_only_repository",),
        )
        compiled = PromptCompiler().compile(task)
        self.assertEqual(compiled.schema, "merlin-engineered-prompt/1")
        self.assertEqual(compiled.authority_scope, "draft_only")
        self.assertIn(unit.unit_id, compiled.prompt_text)
        self.assertIn("Do not claim competency mastery", compiled.prompt_text)

    def test_unknown_role_and_domain_are_rejected(self):
        with self.assertRaises(ValueError):
            build_training_plan("superuser", "mathematics_formal_sciences")
        with self.assertRaises(ValueError):
            build_training_plan("hermes_teacher", "unknown_domain")

    def test_independent_level_requires_independent_evidence(self):
        unit = CurriculumUnit(
            unit_id="bad-capstone", agent_role="domain_researcher",
            domain_family="physics_astronomy", competency_id="research.replication",
            level="independent", objectives=("Do research.",),
            practice_tasks=("Run a test.",), assessment_methods=("quiz",),
            required_evidence=("lesson artifact",),
        )
        with self.assertRaises(ValueError):
            unit.validate()

    def test_passed_record_requires_evidence(self):
        record = {
            "agent_id": "hermes", "unit_id": "hermes.physics.01",
            "level": "foundation", "assessment_status": "passed",
            "evidence_refs": [], "assessor_id": "coder-teacher",
            "assessed_at": "2026-11-05T00:00:00Z",
        }
        with self.assertRaises(ValueError):
            validate_training_record(record)

    def test_independent_pass_requires_replication_and_external_review(self):
        record = {
            "agent_id": "expert-robot", "unit_id": "robot.physics.capstone",
            "level": "independent", "assessment_status": "passed",
            "evidence_refs": ["artifact:result.json"], "assessor_id": "human-reviewer",
            "assessed_at": "2026-11-05T00:00:00Z",
        }
        with self.assertRaises(ValueError):
            validate_training_record(record)
        record["independent_replication_ref"] = "artifact:replication.json"
        record["external_review_ref"] = "review:123"
        validate_training_record(record)


if __name__ == "__main__":
    unittest.main()
