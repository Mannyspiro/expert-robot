"""PII-free business workflow prototype; no external side effects."""
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from datetime import datetime, timezone
from uuid import uuid4
import json

class Stage(str, Enum):
    INTAKE="intake"
    SCHEDULED="scheduled"
    IN_SERVICE="in_service"
    COMPLETED="completed"
    FOLLOW_UP="follow_up"
    CLOSED="closed"

NEXT={
    Stage.INTAKE:{Stage.SCHEDULED},
    Stage.SCHEDULED:{Stage.IN_SERVICE,Stage.INTAKE},
    Stage.IN_SERVICE:{Stage.COMPLETED},
    Stage.COMPLETED:{Stage.FOLLOW_UP,Stage.CLOSED},
    Stage.FOLLOW_UP:{Stage.CLOSED},
    Stage.CLOSED:set(),
}
SERVICES={"document_signing","insurance_quote","workshop","general"}

@dataclass
class Case:
    id:str
    service:str
    stage:Stage=Stage.INTAKE
    events:list=field(default_factory=list)
    head:str="0"*64

    @classmethod
    def open(cls,service):
        if service not in SERVICES: raise ValueError("unsupported service")
        return cls(str(uuid4()),service)

    def move(self,to,actor,approved=False):
        to=Stage(to)
        if not actor or not actor.strip(): raise ValueError("actor required")
        if to not in NEXT[self.stage]: raise ValueError("invalid transition")
        if to in (Stage.COMPLETED,Stage.CLOSED) and not approved:
            raise PermissionError("human approval required")
        event={"case":self.id,"from":self.stage.value,"to":to.value,"actor":actor,
               "at":datetime.now(timezone.utc).isoformat(),"prev":self.head}
        digest=sha256(json.dumps(event,sort_keys=True).encode()).hexdigest()
        self.events.append({**event,"hash":digest})
        self.head=digest
        self.stage=to
        return self.events[-1]

    def verify(self):
        head="0"*64
        stage=Stage.INTAKE
        for event in self.events:
            payload={k:v for k,v in event.items() if k!="hash"}
            digest=sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
            if (event["hash"]!=digest or event["prev"]!=head
                or event["case"]!=self.id or event["from"]!=stage.value
                or Stage(event["to"]) not in NEXT[stage]): return False
            stage=Stage(event["to"])
            head=digest
        return head==self.head and stage==self.stage
