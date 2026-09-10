import pytest
from fastapi.testclient import TestClient
from app.main import app,limiter
from app.services.consistency import ConsistencyEngine
client=TestClient(app)
@pytest.fixture(autouse=True)
def reset_rate_limit():limiter._events.clear()
def test_rule_engine_distinguishes_fail_not_verifiable_and_llm_suggestion():
    result=ConsistencyEngine().validate({"region":"HAND_WRIST","dicom_metadata":{"Modality":"DX","BodyPartExamined":"CHEST"},"quality_status":"REJECT","analysis_status":"COMPLETED","llm_answer":"text"})
    assert result["high_risk_block"] and result["summary"]["FAIL"]>=2 and result["summary"]["NOT_VERIFIABLE"]>=1
    assert any(x["validation_type"]=="LLM_SUGGESTED_FINDING" and x["status"]!="PASS" for x in result["findings"])
def test_validation_api_persists_findings_and_resolution_requires_reason():
    created=client.post("/api/v1/consistency/validate",headers={"X-Role":"QA_RA","X-Request-ID":"consistency-test"},json={"scope":"FULL","target_type":"SYNTHETIC","context":{"region":"HAND_WRIST","dicom_metadata":{"Modality":"DX","BodyPartExamined":"CHEST"}}});assert created.status_code==200;data=created.json();assert data["validation_run_id"] and data["high_risk_block"]
    detail=client.get(f'/api/v1/consistency/runs/{data["validation_run_id"]}').json();finding=next(x for x in detail["findings"] if x["status"]=="FAIL")
    assert client.patch(f'/api/v1/consistency/findings/{finding["finding_id"]}',headers={"X-Role":"QA_RA"},json={"resolved":True}).status_code==422
    resolved=client.patch(f'/api/v1/consistency/findings/{finding["finding_id"]}',headers={"X-Role":"QA_RA","X-User-ID":"qa"},json={"resolved":True,"assigned_role":"QA_RA","comment":"근거 확인","change_reason":"합성 시험에서 수정 완료","resolution_evidence":{"test_id":"SYN-1"}}).json();assert resolved["resolved"] and not resolved["automatic_data_modification"]
def test_knowledge_unavailable_is_not_pass_and_dashboard_counts():
    result=client.post("/api/v1/consistency/knowledge/validate",headers={"X-Role":"ADMIN"}).json();finding=result["findings"][0];assert finding["status"] in {"PASS","FAIL","NOT_VERIFIABLE"}
    if finding["actual"] and finding["actual"].get("connection")!="CONNECTED":assert finding["status"]=="NOT_VERIFIABLE"
    dashboard=client.get("/api/v1/consistency/dashboard").json();assert "unresolved_high_critical" in dashboard and dashboard["qdrant_orphan_vectors"]=="NOT_VERIFIABLE"
def test_model_and_report_high_risk_failures_block_without_modification():
    report=client.post("/api/v1/consistency/reports/report-1/validate",headers={"X-Role":"QA_RA"},json={"analysis_id":"analysis-1","report_manifest":{"analysis_id":"wrong","research_or_dummy_label":False}}).json();assert report["high_risk_block"] and "MARK_REPORT_REGENERATION_REQUIRED" in report["automatic_actions"]
    assert client.post("/api/v1/consistency/models/missing/validate",headers={"X-Role":"ML_ENGINEER"}).status_code==404
def test_rule_catalog_uses_required_prefixes():
    rules=client.get("/api/v1/consistency/rules").json();assert rules and all(x["rule_id"].startswith(("CON-","AUTH-","MON-","MODEL-OPS-")) and x["version"] for x in rules)
