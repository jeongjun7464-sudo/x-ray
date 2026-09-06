from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app, limiter

client=TestClient(app)
def png(value):
    out=BytesIO();Image.new("L",(64,64),value).save(out,"PNG");return out.getvalue()
def analyze(value):
    limiter._events.clear();return client.post("/api/v1/xray/analyze",files={"file":("x.png",png(value),"image/png")}).json()

def test_longitudinal_comparison_marks_acquisition_mismatch_and_review():
    prior,current=analyze(90),analyze(140);limiter._events.clear()
    response=client.post("/api/v1/xray/longitudinal-comparisons",headers={"X-Role":"REVIEWER"},json={"prior_analysis_id":prior["analysis_id"],"current_analysis_id":current["analysis_id"],"prior_context":{"view_position":"PA","resolution":"1024x1024","equipment":"A"},"current_context":{"view_position":"AP","resolution":"2048x2048","equipment":"B"}})
    assert response.status_code==200;data=response.json();assert data["compatibility"]["status"]=="LIMITED" and data["review_required"]
    assert set(data["compatibility"]["mismatches"])=={"view_position","resolution","equipment"}

def test_clinical_correction_creates_anonymous_manual_candidate():
    result=analyze(120);limiter._events.clear()
    reviewed=client.patch(f'/api/v1/xray/analyses/{result["analysis_id"]}/review',headers={"X-Role":"REVIEWER"},json={"final_region":"CHEST","final_findings":["LUNG_OPACITY"],"comment":"reviewed"})
    assert reviewed.status_code==200 and reviewed.json()["automatic_retraining"] is False
    limiter._events.clear();candidates=client.get("/api/v1/active-learning/candidates",headers={"X-Role":"REVIEWER"}).json()
    candidate=next(x for x in candidates if x["analysis_id"]==result["analysis_id"]);assert len(candidate["anonymous_hash"])==64 and candidate["automatic_retraining"] is False

def test_dataset_patient_split_duplicate_manifest_and_approval_gate():
    h1="a"*64;h2="b"*64;p="c"*64;limiter._events.clear()
    response=client.post("/api/v1/datasets",headers={"X-Role":"ADMIN"},json={"name":"synthetic","version":"v1","items":[{"anonymous_hash":h1,"patient_hash":p,"region":"CHEST","findings":["B","A"],"label_status":"APPROVED"},{"anonymous_hash":h1,"patient_hash":p,"region":"CHEST"},{"anonymous_hash":h2,"patient_hash":p,"region":"CHEST","findings":[],"label_status":"APPROVED"}]})
    assert response.status_code==200;data=response.json();assert data["duplicates_removed"]==1 and len(data["items"])==2
    assert len({x["split"] for x in data["items"]})==1
    limiter._events.clear();assert client.post(f'/api/v1/datasets/{data["dataset_id"]}/approve',headers={"X-Role":"ADMIN"}).json()["status"]=="APPROVED"
    limiter._events.clear();csv_response=client.get(f'/api/v1/datasets/{data["dataset_id"]}/manifest.csv');assert "anonymous_hash" in csv_response.text and h1 in csv_response.text

def test_failure_analysis_does_not_invent_metrics_without_validation_data():
    limiter._events.clear();data=client.post("/api/v1/failure-analysis",headers={"X-Role":"ADMIN"},json={"validated_cases":[]}).json()
    assert data["status"]=="NOT_MEASURED" and data["confusion_matrix"] is None

def test_model_monitoring_hash_and_regulatory_documents():
    limiter._events.clear();created=client.post("/api/v1/model-monitoring/deployments",headers={"X-Role":"ADMIN"},json={"model_version":"dummy-v2","checkpoint_sha256":"d"*64,"dataset_version":"synthetic-v1","deployment_status":"DEMO_ONLY"})
    assert created.status_code==200 and created.json()["performance_status"]=="NOT_MEASURED" and created.json()["drift_status"]=="INSUFFICIENT_DATA"
    limiter._events.clear();docs=client.get("/api/v1/regulatory-documents").json();assert len(docs)==6
    limiter._events.clear();content=client.get("/api/v1/regulatory-documents/SRS.md");assert content.status_code==200 and "NOT_MEASURED" in content.text
