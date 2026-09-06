from dataclasses import asdict,dataclass
from typing import Protocol

class LLMError(RuntimeError):
    def __init__(self,code:str,message:str):super().__init__(message);self.code=code
@dataclass
class LLMResponse:
    content:str;model_name:str;model_version:str;provider:str;prompt_tokens:int;completion_tokens:int;latency_ms:float;finish_reason:str;dummy_mode:bool;request_id:str
    def dict(self):return asdict(self)
class LLMClient(Protocol):
    def generate(self,messages:list[dict],temperature:float,max_tokens:int,request_id:str)->LLMResponse:...
