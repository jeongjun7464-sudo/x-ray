from .base import ConsistencyRule
from .registry import register
@register
class QualityRejectRule(ConsistencyRule):
    rule_id="CON-QUALITY-001";category="QUALITY_ANALYSIS";severity="CRITICAL"
    def check(self,c):
        quality=c.get("quality_status");completed=c.get("analysis_status")=="COMPLETED"
        if not quality:return self.finding("NOT_VERIFIABLE","품질 상태가 없습니다.")
        fail=quality=="REJECT" and completed;return self.finding("FAIL" if fail else "PASS","품질 REJECT 영상의 완료 상태를 확인했습니다.","REJECT 영상 자동 완료 금지",{"quality":quality,"analysis_status":c.get("analysis_status")},action="BLOCK_AUTO_APPROVAL" if fail else "NONE",review=fail)
