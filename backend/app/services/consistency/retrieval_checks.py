from .base import ConsistencyRule
from .registry import register
@register
class CitationRule(ConsistencyRule):
    rule_id="CON-RAG-001";category="RAG_EVIDENCE";severity="HIGH"
    def check(self,c):
        citations={(x.get("document_id"),x.get("version"),x.get("section"),x.get("chunk_id")) for x in c.get("citations",[])};retrieved={(x.get("document_id"),x.get("version"),x.get("section"),x.get("chunk_id")) for x in c.get("retrieved_documents",[])}
        if not citations and not retrieved:return self.finding("NOT_VERIFIABLE","검색 및 citation 기록이 없습니다.")
        invalid=citations-retrieved;return self.finding("FAIL" if invalid else "PASS","모든 citation이 실제 검색 결과에 포함되는지 확인했습니다.","검색 결과에 포함된 citation",list(invalid),action="ROUTE_TO_REVIEW" if invalid else "NONE",review=bool(invalid))
