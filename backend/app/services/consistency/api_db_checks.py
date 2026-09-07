from .base import ConsistencyRule
from .registry import register
@register
class ApiDisplayRule(ConsistencyRule):
    rule_id="CON-API-001";category="API_DB_UI";severity="HIGH"
    def check(self,c):
        api=c.get("api_state");ui=c.get("ui_state")
        if api is None or ui is None:return self.finding("NOT_VERIFIABLE","API 또는 화면 상태 증적이 없습니다.")
        fail=api.get("review_required") and ui.get("status")=="COMPLETED";return self.finding("FAIL" if fail else "PASS","검토 필요 상태의 화면 표시를 확인했습니다.",api,ui,action="ROUTE_TO_REVIEW" if fail else "NONE",review=fail)
