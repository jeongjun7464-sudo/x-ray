"""Index governed Markdown knowledge into Qdrant; falls back without failing the API."""
from app.services.retrieval.document_ingestion import load_documents,qdrant_points
from app.services.retrieval.qdrant_store import QdrantStore
def main():
    chunks,errors=load_documents();result={"documents_with_errors":errors,"chunks":len(chunks)}
    try:QdrantStore().upsert(qdrant_points(chunks));result["retrieval_mode"]="QDRANT"
    except Exception as exc:result.update(retrieval_mode="LOCAL_FALLBACK",error=type(exc).__name__)
    print(result)
if __name__=="__main__":main()
