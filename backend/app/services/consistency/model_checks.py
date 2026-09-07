from .base import ConsistencyRule
from .registry import register
@register
class ModelIdentityRule(ConsistencyRule):
    rule_id="CON-MODEL-001";category="MODEL_INPUT";severity="HIGH"
    def check(self,c):
        model=c.get("model",{});required=("version","checkpoint_sha256","dummy_mode")
        missing=[x for x in required if model.get(x) is None]
        return self.finding("NOT_VERIFIABLE" if missing else "PASS","모델 버전·체크포인트·dummy 표시를 확인했습니다.",list(required),missing or "complete",action="BLOCK_AUTO_APPROVAL" if missing else "NONE",review=bool(missing))
