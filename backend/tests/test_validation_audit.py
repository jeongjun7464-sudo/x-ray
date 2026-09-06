from io import BytesIO
import hashlib,zipfile,uuid
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app,limiter

client=TestClient(app)
def png(value=120):
    out=BytesIO();Image.new("L",(64,64),value).save(out,"PNG");return out.getvalue()
def test_provenance_compare_and_explicit_reproduction_block():
    limiter._events.clear();a=client.post("/api/v1/xray/analyze",files={"file":("a.png",png(),"image/png")}).json();limiter._events.clear();b=client.post("/api/v1/xray/analyze",files={"file":("b.png",png(),"image/png")}).json()
    provenance=client.get(f'/api/v1/analyses/{a["analysis_id"]}/provenance').json()
    assert len(provenance["input_sha256"])==64 and provenance["random_seed"] is not None and provenance["raw_input_retained"] is False
    assert client.post(f'/api/v1/analyses/{a["analysis_id"]}/reproduce',headers={"X-Role":"ML_ENGINEER"}).status_code==409
    compared=client.get(f'/api/v1/analyses/{a["analysis_id"]}/compare/{b["analysis_id"]}').json();assert compared["same_input"] and compared["same_settings"] and compared["review_required"]

def test_scenario_execution_and_synthetic_safety_contract():
    key=uuid.uuid4().hex;headers={"X-Role":"QA_RA"}
    req=client.post("/api/v1/test-requirements",headers=headers,json={"requirement_id":"REQ-"+key,"risk_ids":["RISK-SEC"],"title":"upload security"});assert req.status_code==200
    scenario=client.post("/api/v1/test-scenarios",headers=headers,json={"test_id":"TEST-"+key,"requirement_id":"REQ-"+key,"risk_ids":["RISK-SEC"],"scenario_type":"SECURITY","preconditions":"synthetic only","input_data":{"case":"WRONG_MODALITY"},"steps":["generate","upload"],"expected_result":"rejected"}).json()
    executed=client.post(f'/api/v1/test-scenarios/{scenario["scenario_id"]}/executions',headers=headers,json={"status":"FAIL","actual_result":"unexpected","tester":"qa","evidence":[{"filename":"log.txt","sha256":hashlib.sha256(b"log").hexdigest()}],"defect_summary":"unexpected acceptance"}).json();assert executed["defect_created"]
    cases=client.get("/api/v1/synthetic-safety-cases").json();assert len(cases)==15
    generated=client.post("/api/v1/synthetic-safety-cases/WRONG_MODALITY");assert generated.status_code==200 and generated.headers["X-Expected-Error"]=="UNSUPPORTED_MODALITY"

def test_independent_annotation_adjudication_and_approval():
    digest=hashlib.sha256(b"synthetic image").hexdigest()
    first=client.post("/api/v1/annotations",headers={"X-Role":"LABELER","X-Actor":"labeler-a"},json={"anonymous_image_hash":digest,"region":"CHEST","findings":[]}).json()
    second=client.post(f'/api/v1/annotations/{first["annotation_id"]}/second-review',headers={"X-Role":"RADIOLOGIST","X-Actor":"reader-b"},json={"region":"KNEE","findings":[]}).json();assert second["status"]=="DISAGREEMENT"
    adjudicated=client.post(f'/api/v1/annotations/{first["annotation_id"]}/adjudicate',headers={"X-Role":"ADJUDICATOR","X-Actor":"adjudicator-c"},json={"region":"CHEST","findings":[],"reason":"consensus"});assert adjudicated.status_code==200
    approved=client.post(f'/api/v1/annotations/{first["annotation_id"]}/approve',headers={"X-Role":"ADJUDICATOR"}).json();assert approved["training_eligible"]
    agreement=client.get("/api/v1/annotations/agreement").json();assert agreement["sample_size"]>=1

def test_fairness_requires_samples_and_reports_measured_values_only():
    headers={"X-Role":"ML_ENGINEER"};small=client.post("/api/v1/fairness/evaluate",headers=headers,json={"group_by":"sex","min_samples":2,"validated_cases":[{"sex":"F","truth":True,"prediction":True,"score":.9}]}).json();assert small["groups"][0]["status"]=="INSUFFICIENT_DATA"
    cases=[{"sex":"F","truth":True,"prediction":True,"score":.9},{"sex":"F","truth":False,"prediction":False,"score":.1}]
    measured=client.post("/api/v1/fairness/evaluate",headers=headers,json={"group_by":"sex","min_samples":2,"validated_cases":cases}).json()["groups"][0];assert measured["sample_size"]==2 and measured["metrics"]["auroc"]==1

def test_recovery_idempotency_backoff_and_permissions():
    key="recovery-"+uuid.uuid4().hex;headers={"X-Role":"TECHNICIAN","Idempotency-Key":key,"X-Request-ID":"request-1"}
    first=client.post("/api/v1/recovery/jobs",headers=headers,json={"simulate_failure":"MODEL_SERVER_DOWN","max_attempts":3}).json();assert first["status"]=="RETRY_PENDING" and first["routed_to_medical_review"]
    duplicate=client.post("/api/v1/recovery/jobs",headers=headers,json={"simulate_failure":"MODEL_SERVER_DOWN"}).json();assert duplicate["duplicate"]
    assert client.post(f'/api/v1/recovery/jobs/{first["job_id"]}/retry',headers={"X-Role":"TECHNICIAN"},json={}).status_code==403
    retry=client.post(f'/api/v1/recovery/jobs/{first["job_id"]}/retry',headers={"X-Role":"ADMIN"},json={}).json();assert retry["next_retry_seconds"]==4

def test_audit_package_content_integrity_and_security_status():
    created=client.post("/api/v1/audit-packages",headers={"X-Role":"QA_RA","X-Request-ID":"audit-request"},json={"versions":{"application":"0.1.0","dataset":"synthetic-v1"}});assert created.status_code==200;data=created.json();assert len(data["manifest"]["files"])==9
    downloaded=client.get(f'/api/v1/audit-packages/{data["package_id"]}/download');assert hashlib.sha256(downloaded.content).hexdigest()==data["package_sha256"]
    with zipfile.ZipFile(BytesIO(downloaded.content)) as archive:
        assert set(archive.namelist())=={"requirements.pdf","risk-management.xlsx","dataset-specification.pdf","model-card.pdf","validation-report.pdf","approval-history.csv","change-history.csv","capa-records.csv","traceability-matrix.xlsx","manifest.json"}
        with zipfile.ZipFile(BytesIO(archive.read("risk-management.xlsx"))) as workbook:assert "xl/worksheets/sheet1.xml" in workbook.namelist()
    security=client.get("/api/v1/security/status").json();assert security["malware_scanner"]=="NOT_CONFIGURED" and security["malware_scan_completed"] is False
