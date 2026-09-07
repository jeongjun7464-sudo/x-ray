from .base import ConsistencyRule
from .registry import register
@register
class ReportRule(ConsistencyRule):
    rule_id="CON-REPORT-001";category="REPORT_RESULT";severity="HIGH"
    def check(self,c):
        report=c.get("report")
        if report is None:return self.finding("NOT_VERIFIABLE","보고서 manifest가 없습니다.")
        expected=c.get("analysis_id");fail=report.get("analysis_id")!=expected or not report.get("research_or_dummy_label")
        return self.finding("FAIL" if fail else "PASS","보고서 분석 ID와 연구용 표시를 확인했습니다.",expected,report,action="MARK_REPORT_REGENERATION_REQUIRED" if fail else "NONE",review=fail)
