from .base import ConsistencyRule
from .registry import register
@register
class LLMSemanticSuggestionRule(ConsistencyRule):
    rule_id="CON-LLM-001";category="LLM_EVIDENCE";severity="MEDIUM"
    def check(self,c):
        if not c.get("llm_answer"):return self.finding("NOT_APPLICABLE","sLLM 답변이 없습니다.")
        return self.finding("MANUAL_REVIEW_REQUIRED","sLLM 의미 일치 검사는 자동 PASS로 처리하지 않습니다.",actual="LLM_SUGGESTED_FINDING",review=True,validation_type="LLM_SUGGESTED_FINDING")
