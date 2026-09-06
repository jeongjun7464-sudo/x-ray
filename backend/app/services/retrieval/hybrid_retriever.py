from datetime import date
from app.core.config import settings
from .bm25_store import BM25Store
from .document_ingestion import load_documents
from .embedding_client import EmbeddingClient
from .qdrant_store import QdrantStore
from .reranker import rerank
class HybridRetriever:
    def __init__(self):self.documents,self.load_errors=load_documents();self.qdrant=QdrantStore();self.bm25=BM25Store()
    def _allowed(self,d,role,institution):
        expires=d.get("expires_at");return d.get("approval_status")=="APPROVED" and role in d.get("allowed_roles",[]) and d.get("institution_id") in {institution,"GLOBAL"} and not d.get("deleted") and (not expires or expires>=date.today().isoformat())
    def search(self,query,role,institution="DEMO"):
        docs=[x for x in self.documents if self._allowed(x,role,institution)];bm=self.bm25.search(query,docs,settings.retrieval_top_k);mode="QDRANT_HYBRID"
        try:vec=self.qdrant.search(EmbeddingClient().embed(query),{"approval_status":"APPROVED","institution_id":institution},settings.retrieval_top_k);vec=[x for x in vec if self._allowed(x,role,institution)]
        except Exception:vec=[];mode="LOCAL_FALLBACK"
        ranks={}
        for source,key in ((bm,"bm25_rank"),(vec,"vector_rank")):
            for rank,item in enumerate(source,1):ranks.setdefault(item["chunk_id"],item)[key]=rank
        for item in ranks.values():item["rrf_score"]=sum(1/(settings.rrf_k+item[k]) for k in ("bm25_rank","vector_rank") if item.get(k))
        ordered=rerank(query,list(ranks.values()));selected=[];counts={}
        for item in ordered:
            if counts.get(item["document_id"],0)>=2:continue
            if item["rrf_score"]<1/(settings.rrf_k+settings.retrieval_top_k):continue
            selected.append(item);counts[item["document_id"]]=counts.get(item["document_id"],0)+1
            if len(selected)>=settings.retrieval_final_k:break
        return {"status":"COMPLETED" if selected else "NO_EVIDENCE","mode":mode,"results":selected,"load_errors":self.load_errors}
