from .base import ConsistencyRule
from .registry import register
from app.services.retrieval.security import contains_phi
@register
class PromptSecurityRule(ConsistencyRule):
    rule_id="CON-SECURITY-001";category="SECURITY";severity="CRITICAL"
    def check(self,c):
        prompt=str(c.get("prompt_snapshot","") or "")
        if not prompt:return self.finding("NOT_VERIFIABLE","Prompt 증적이 저장되지 않았습니다.")
        phi=contains_phi(prompt);return self.finding("FAIL" if phi else "PASS","Prompt 개인정보 포함 여부를 확인했습니다.","개인정보 없음","PHI_DETECTED" if phi else "clean",action="BLOCK_AUTO_APPROVAL" if phi else "NONE",review=phi)
