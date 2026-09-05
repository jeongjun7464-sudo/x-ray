from dataclasses import asdict,dataclass

@dataclass(frozen=True)
class FindingPrediction:
    code:str;display_name:str;probability:float;threshold:float;positive:bool
    def dict(self):return asdict(self)

@dataclass(frozen=True)
class FindingResult:
    findings:list[FindingPrediction];model_name:str;model_version:str;checkpoint_hash:str|None;dummy_mode:bool;explanation_available:bool
    def dict(self):return {**asdict(self),"findings":[x.dict() for x in self.findings]}
