from abc import ABC,abstractmethod
from .schemas import ConsistencyFinding
class ConsistencyRule(ABC):
    rule_id="CON-BASE-000";version="1.0";category="BASE";severity="INFO"
    @abstractmethod
    def check(self,context)->ConsistencyFinding:...
    def finding(self,status,message,expected=None,actual=None,evidence=None,action="NONE",review=False,validation_type="RULE_BASED"):
        return ConsistencyFinding(self.rule_id,self.version,self.category,status,self.severity,message,expected,actual,evidence or [],action,review,validation_type)
