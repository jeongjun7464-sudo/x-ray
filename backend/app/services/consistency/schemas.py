from dataclasses import asdict,dataclass,field
from datetime import datetime,timezone
import uuid
STATUSES={"PASS","WARNING","FAIL","NOT_APPLICABLE","NOT_VERIFIABLE","BLOCKED","MANUAL_REVIEW_REQUIRED"}
SEVERITIES={"INFO","LOW","MEDIUM","HIGH","CRITICAL"}
@dataclass
class ConsistencyFinding:
    rule_id:str;rule_version:str;category:str;status:str;severity:str;message:str;expected:object=None;actual:object=None;evidence:list=field(default_factory=list);automatic_action:str="NONE";requires_human_review:bool=False;validation_type:str="RULE_BASED";finding_id:str=field(default_factory=lambda:str(uuid.uuid4()));created_at:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
    def dict(self):return asdict(self)
