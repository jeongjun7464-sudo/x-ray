import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.services.llm.dummy_client import DummyLLMClient
from app.services.llm.output_parser import parse_output,verify_citations
from app.services.retrieval.document_ingestion import load_documents
from app.services.retrieval.hybrid_retriever import HybridRetriever
from app.services.retrieval.security import validate_document
client=TestClient(app)
def test_dummy_llm_is_reproducible_and_schema_valid():
    llm=DummyLLMClient();messages=[{"role":"user","content":"EVIDENCE|D|1|S|C|text"}]
    a=llm.generate(messages,.1,100,"a");b=llm.generate(messages,.1,100,"b");assert a.content==b.content and a.dummy_mode
    parsed=parse_output(a.content);verified=verify_citations(parsed,[{"document_id":"D","version":"1","section":"S","chunk_id":"C"}]);assert verified["evidence"]
def test_governed_documents_and_phi_block():
    docs,errors=load_documents();assert not errors and docs and all(x["approval_status"]=="APPROVED" for x in docs)
    try:validate_document("PatientName: Kim")
    except ValueError as exc:assert "PHI_DETECTED" in str(exc)
    else:raise AssertionError("PHI should be blocked")
def test_hybrid_falls_back_and_filters_roles(monkeypatch):
    retriever=HybridRetriever();monkeypatch.setattr(retriever.qdrant,"search",lambda *a,**k:(_ for _ in ()).throw(ConnectionError()))
    found=retriever.search("품질 검사","USER","DEMO");assert found["mode"]=="LOCAL_FALLBACK" and found["results"]
    restricted=retriever.search("CAPA 근본원인","USER","DEMO");assert all(x["document_id"]!="DOC-DEMO-CAPA-001" for x in restricted["results"])
def test_v1_agent_grounded_response_trace_and_status():
    result=client.post("/api/v1/agent/chat",headers={"X-Role":"REVIEWER","X-User-ID":"demo"},json={"question":"영상 품질 검토 절차를 알려줘"});assert result.status_code==200;data=result.json();assert data["response_status"] in {"COMPLETED","DEGRADED"} and data["evidence"] and data["requires_human_review"]
    trace=client.get(f'/api/v1/agent/runs/{data["trace_id"]}',headers={"X-Role":"ADMIN"});assert trace.status_code==200 and trace.json()["masked_query"]
def test_no_evidence_and_admin_status_do_not_expose_secrets():
    response=client.post("/api/v1/agent/chat",headers={"X-Role":"USER"},json={"question":"화성 기지의 승인되지 않은 미지 문서"}).json();assert response["response_status"] in {"NO_EVIDENCE","DEGRADED"}
    llm=client.get("/api/v1/admin/llm/status",headers={"X-Role":"ADMIN"}).json();assert not llm["api_key_exposed"] and not llm["base_url_exposed"]
    qdrant=client.get("/api/v1/admin/qdrant/status",headers={"X-Role":"ADMIN"}).json();assert "connection_status" in qdrant
def test_index_deduplicates_and_requires_role():
    assert client.post("/api/v1/admin/knowledge/index",headers={"X-Role":"USER"}).status_code==403
    first=client.post("/api/v1/admin/knowledge/index",headers={"X-Role":"QA_RA","X-Request-ID":uuid.uuid4().hex}).json();second=client.post("/api/v1/admin/knowledge/index",headers={"X-Role":"QA_RA"}).json();assert first["retrieval_mode"] in {"QDRANT","LOCAL_FALLBACK"} and second["skipped_duplicates"]>=first["indexed"]
