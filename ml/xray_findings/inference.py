from __future__ import annotations
import hashlib
from .postprocess import apply_thresholds
from .schemas import FindingResult
from .thresholds import DEFAULT_THRESHOLDS,FINDING_LABELS

class FindingInferenceEngine:
    def __init__(self,model=None,version:str="dummy-finding-v1",checkpoint_hash:str|None=None,thresholds:dict[str,float]|None=None):
        self.model=model;self.version=version;self.checkpoint_hash=checkpoint_hash;self.thresholds=thresholds or DEFAULT_THRESHOLDS.copy();self.dummy_mode=model is None
    def predict(self,image_bytes:bytes)->FindingResult:
        if not self.dummy_mode:raise NotImplementedError("실제 체크포인트 전처리 어댑터가 설정되지 않았습니다.")
        digest=hashlib.sha256(image_bytes).digest();probs={code:(digest[i%len(digest)]+1)/257 for i,code in enumerate(FINDING_LABELS)}
        return FindingResult(apply_thresholds(probs,self.thresholds),"deterministic-multilabel-dummy",self.version,None,True,False)
