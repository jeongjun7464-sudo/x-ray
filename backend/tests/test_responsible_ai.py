from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient
import pytest
from app.main import app, limiter
from app.services.responsible_ai import CONSENT_ITEMS, percentile

client=TestClient(app)

@pytest.fixture(autouse=True)
def reset_rate_limit():
    limiter._events.clear()

def image_bytes():
    out=BytesIO(); Image.new("L",(64,64),128).save(out,"PNG"); return out.getvalue()

def test_transparency_content_and_cards():
    info=client.get("/api/ai-literacy/transparency").json()
    assert info["dummy_model"] is True and info["approval_status"]=="DEMO_ONLY" and info["diagnostic_use"] is False
    assert client.get("/api/ai-literacy/model-cards").json()[0]["metrics"] is None
    assert client.get("/api/ai-literacy/dataset-cards").json()[0]["image_count"] is None
    confidence=client.get("/api/ai-literacy/confidence/0.95").json()
    assert confidence["level"]=="HIGH" and "정확도" in confidence["not_accuracy"]

def test_consent_version_is_recorded():
    body={"anonymous_user_id":"synthetic-user","consent_version":"ai-literacy-v1.0","accepted_items":CONSENT_ITEMS,"accepted":True}
    result=client.post("/api/ai-literacy/consent",json=body)
    assert result.status_code==200 and result.json()["version"]=="ai-literacy-v1.0" and result.json()["confirmed_at"]

def test_latency_measurement_and_p95():
    assert percentile([10,20,30,40,50],.95)==48
    prediction=client.post("/api/predictions",files={"file":("phase23.png",image_bytes(),"image/png")})
    assert prediction.status_code==200
    latency=client.get("/api/ai-literacy/latency").json()
    assert latency["count"]>=1 and latency["p95"]>=0
    assert {"file_upload","dicom_decode","deidentification","preprocessing","ai_inference","gradcam","database_save"}.issubset(latency["latest_stages"])

def test_misclassification_report_forces_human_review():
    prediction=client.post("/api/predictions",files={"file":("report.png",image_bytes(),"image/png")}).json()
    report=client.post("/api/ai-literacy/reports",json={"prediction_id":prediction["prediction_id"],"report_type":"POSSIBLE_PRIVACY_EXPOSURE","description":"합성 개인정보 경고 테스트"})
    assert report.status_code==200 and report.json()["review_required"] and report.json()["capa_candidate"]
    refreshed=client.get(f'/api/predictions/{prediction["prediction_id"]}').json()
    assert refreshed["review_required"] and "USER_REPORT" in refreshed["review_reasons"]

def test_responsible_dashboard_and_risk_registry():
    dashboard=client.get("/api/ai-literacy/dashboard").json()
    assert "review_required_rate" in dashboard and dashboard["dataset_performance"].startswith("실제")
    risks=client.get("/api/ai-literacy/risks").json()
    assert len(risks)==12 and all(x["verification_test"] for x in risks)

def test_glossary_includes_privacy_and_ai_terms():
    terms={x["term"] for x in client.get("/api/ai-literacy/glossary").json()}
    assert {"Confidence","Accuracy","Grad-CAM","DICOM","Human-in-the-loop","Audit Log"}.issubset(terms)
