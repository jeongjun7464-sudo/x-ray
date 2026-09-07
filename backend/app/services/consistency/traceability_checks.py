from .base import ConsistencyRule
from .registry import register
@register
class TraceabilityRule(ConsistencyRule):
    rule_id="CON-TRACE-001";category="TRACEABILITY";severity="HIGH"
    def check(self,c):
        item=c.get("traceability")
        if item is None:return self.finding("NOT_VERIFIABLE","추적성 항목이 제공되지 않았습니다.")
        missing=[x for x in ("requirement_id","risk_id","test_id","test_result") if not item.get(x)];failed=item.get("test_result")=="FAIL"
        return self.finding("FAIL" if missing or failed else "PASS","요구사항·위험·시험 연결을 확인했습니다.","필수 연결과 PASS",missing or item.get("test_result"),action="BLOCK_AUTO_APPROVAL" if missing or failed else "NONE",review=bool(missing or failed))
