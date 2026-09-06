from dataclasses import asdict,dataclass
@dataclass
class HybridSearchResult:
    document_id:str;chunk_id:str;title:str;version:str;section:str;content:str;source_path:str;approval_status:str;bm25_rank:int|None=None;vector_rank:int|None=None;rrf_score:float=0;rerank_score:float|None=None
    def dict(self):return asdict(self)
