from .base import ConsistencyRule
from .registry import register
@register
class ReviewCompletionRule(ConsistencyRule):
    rule_id="CON-REVIEW-001";category="CLINICAL_REVIEW";severity="HIGH"
    def check(self,c):
        if not c.get("review_required"):return self.finding("NOT_APPLICABLE","검토 필요 결과가 아닙니다.")
        review=c.get("review");ok=bool(review and review.get("reviewer") and review.get("role") and review.get("reviewed_at"))
        return self.finding("PASS" if ok else "MANUAL_REVIEW_REQUIRED","검토 완료 필수값을 확인했습니다.","검토자·역할·시각",review,action="ROUTE_TO_REVIEW",review=not ok)
