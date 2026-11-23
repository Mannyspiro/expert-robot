"""Prototype fail-closed agent capability policy; NOT production authentication."""
from enum import Enum

class Agent(str, Enum):
    MERLIN="merlin"
    TITAN="titan"
    ARTEX="artex"

class Action(str, Enum):
    RESEARCH="research"
    PROPOSE_CODE="propose_code"
    REVIEW_BUSINESS="review_business"
    REVIEW_SECURITY="review_security"
    READ_SYNTHETIC="read_synthetic"
    READ_CLIENT="read_client"
    MODIFY_CLIENT="modify_client"
    READ_SECRET="read_secret"
    ROTATE_SECRET="rotate_secret"
    DEPLOY="deploy"
    SEND_MESSAGE="send_message"

PERMISSIONS={
    Agent.MERLIN:{Action.RESEARCH,Action.PROPOSE_CODE,Action.READ_SYNTHETIC},
    Agent.TITAN:{Action.RESEARCH,Action.REVIEW_BUSINESS,Action.READ_SYNTHETIC},
    Agent.ARTEX:{Action.REVIEW_SECURITY,Action.READ_SYNTHETIC},
}

def allowed(agent,action,*,human_approved=False):
    agent,action=Agent(agent),Action(action)
    # Human approval is necessary for some operations but never expands an agent's authority.
    return action in PERMISSIONS[agent]

def require(agent,action,*,human_approved=False):
    if not allowed(agent,action,human_approved=human_approved):
        raise PermissionError("agent action denied")
    return True
