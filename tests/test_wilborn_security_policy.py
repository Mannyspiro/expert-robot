import unittest
from wilborn_ops.security_policy import Agent,Action,allowed,require

class SecurityPolicyTests(unittest.TestCase):
    def test_no_secrets_or_client_data_or_side_effects(self):
        for agent in Agent:
            for action in (Action.READ_SECRET,Action.ROTATE_SECRET,Action.READ_CLIENT,
                           Action.MODIFY_CLIENT,Action.DEPLOY,Action.SEND_MESSAGE):
                self.assertFalse(allowed(agent,action))
                self.assertFalse(allowed(agent,action,human_approved=True))
                with self.assertRaises(PermissionError): require(agent,action)

    def test_frameworks_are_not_agents(self):
        self.assertEqual([agent.value for agent in Agent],["merlin"])
        for non_agent in ("titan","artex"):
            with self.assertRaises(ValueError): Agent(non_agent)
        self.assertTrue(allowed(Agent.MERLIN,Action.PROPOSE_CODE))
