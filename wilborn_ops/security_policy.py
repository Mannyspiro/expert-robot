"""Prototype Merlin capability policy; NOT production authentication.

Titan is encryption; Artex is an LLM cybersecurity framework. Neither is an agent.
"""
from enum import Enum

class Agent(str, Enum):
    MERLIN="merlin"

class Action(str, Enum):
    RESEARCH="research"
    PROPOSE_CODE="propose_code"
    READ_SYNTHETIC="read_synthetic"
    READ_CLIENT="read_client"
    MODIFY_CLIENT="modify_client"
    READ_SECRET="read_secret"
    ROTATE_SECRET="rotate_secret"
    DEPLOY="deploy"
    SEND_MESSAGE="send_message"

PERMISSIONS={
    Agent.MERLIN:{Action.RESEARCH,Action.PROPOSE_CODE,Action.READ_SYNTHETIC},
}

def allowed(agent,action,*,human_approved=False):
    agent,action=Agent(agent),Action(action)
    return action in PERMISSIONS[agent]

def require(agent,action,*,human_approved=False):
    if not allowed(agent,action,human_approved=human_approved):
        raise PermissionError("agent action denied")
    return True
