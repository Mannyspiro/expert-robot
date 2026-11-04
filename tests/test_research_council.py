import unittest
from merlin.research_council import (
    CouncilContribution, CouncilRole, EvidenceClass, PhysicsEnvironment,
    run_council, virtual_chip_budget,
)


class Agent:
    def __init__(self, role, evidence=EvidenceClass.HYPOTHESIS):
        self.role = role
        self.evidence = evidence

    def contribute(self, question, environment, context):
        return CouncilContribution(
            self.role.role_id, f"{self.role.role_id} analysis of {question}",
            self.evidence, assumptions=environment.assumptions,
        )


class ResearchCouncilTests(unittest.TestCase):
    def test_serial_council_and_receipt_are_deterministic(self):
        env = PhysicsEnvironment("thermal", "heat transfer", "ode_pde",
                                 assumptions=("constant properties",))
        agents = (Agent(CouncilRole("skeptic", "challenge", must_challenge=True)),
                  Agent(CouncilRole("mathematician", "derive")))
        session = run_council("estimate heat rise", env, agents)
        self.assertEqual([c.role_id for c in session.contributions],
                         ["mathematician", "skeptic"])
        self.assertEqual(session.canonical_receipt()["sha256"],
                         session.canonical_receipt()["sha256"])
        self.assertEqual(session.status, "RESEARCH_ONLY_NOT_APPROVED")

    def test_rejects_invalid_physics_parameters(self):
        with self.assertRaises(ValueError):
            PhysicsEnvironment("bad", "bad", "ode", parameters={"temperature": float("nan")}).validate()

    def test_virtual_chip_budget_has_explicit_evidence_ceiling(self):
        budget = virtual_chip_budget(8, 2**30, 10**9, 35)
        self.assertEqual(budget["evidence_ceiling"], "resource_estimate_not_chip_physics")
        with self.assertRaises(ValueError):
            virtual_chip_budget(0, 100, 1)


if __name__ == "__main__":
    unittest.main()
