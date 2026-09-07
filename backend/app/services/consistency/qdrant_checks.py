from .base import ConsistencyRule
from .registry import register
@register
class QdrantPayloadRule(ConsistencyRule):
    rule_id="CON-QDRANT-001";category="QDRANT_DOCUMENT";severity="HIGH"
    def check(self,c):
        state=c.get("knowledge_state")
        if state is None:return self.finding("NOT_VERIFIABLE","Qdrant와 DB 상태를 조회할 수 없습니다.")
        orphan=state.get("orphan_points");missing=state.get("missing_vectors")
        if orphan is None or missing is None:return self.finding("NOT_VERIFIABLE","Qdrant 미연결로 vector 정합성을 검증할 수 없습니다.",actual=state)
        fail=orphan>0 or missing>0;return self.finding("FAIL" if fail else "PASS","Qdrant orphan point와 missing vector를 확인했습니다.",{"orphan":0,"missing":0},{"orphan":orphan,"missing":missing},action="DISABLE_DOCUMENT_SEARCH" if fail else "NONE",review=fail)
