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

    def test_separation_of_duties(self):
        self.assertTrue(allowed(Agent.TITAN,Action.REVIEW_BUSINESS))
        self.assertFalse(allowed(Agent.MERLIN,Action.REVIEW_BUSINESS))
        self.assertTrue(allowed(Agent.ARTEX,Action.REVIEW_SECURITY))
        self.assertFalse(allowed(Agent.TITAN,Action.REVIEW_SECURITY))
        self.assertTrue(allowed(Agent.MERLIN,Action.PROPOSE_CODE))
        self.assertFalse(allowed(Agent.ARTEX,Action.PROPOSE_CODE))
