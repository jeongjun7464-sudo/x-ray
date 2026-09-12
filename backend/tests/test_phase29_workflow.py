import uuid
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app, limiter
from app.core.auth import issue_session_token
from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import XrayAnalysis
from app.db.integration_models import ExternalTransferEvent

def test_authenticated_institution_scoped_proposal_confirmation(monkeypatch):
    limiter._events.clear()
    secret = "phase29-test-secret-synthetic-only-at-least-32"
    monkeypatch.setattr(settings, "auth_session_secret", secret)
    monkeypatch.setattr(settings, "integration_principal_institutions", {"qa-synthetic": "A", "other-synthetic": "B"})
    def headers(subject):
        token, _ = issue_session_token(subject, "QA_RA", secret)
        return {"Authorization": "Bearer " + token}
    with SessionLocal() as db:
        analysis = XrayAnalysis(anonymous_hash="a"*64, modality="DX", is_dicom=True,
            quality={}, region_result={"predicted_class": "CHEST"}, screening_status="REVIEW_REQUIRED",
            uncertainty={}, routing={}, model_info={"dummy_mode": True}, reviewed=False)
        db.add(analysis); db.commit(); analysis_id = analysis.id
    monkeypatch.setattr(settings, "integration_resource_institutions", {analysis_id: "A"})
    client = TestClient(app)
    assert client.get("/api/v1/external-transfers").status_code == 401
    key = uuid.uuid4().hex
    payload = {"analysis_id": analysis_id, "destination": "FHIR", "reason": "Synthetic contract test"}
    own = {**headers("qa-synthetic"), "Idempotency-Key": key}
    created = client.post("/api/v1/external-transfers/proposals", json=payload, headers=own)
    assert created.status_code == 201, created.text
    job_id = created.json()["id"]
    replay = client.post("/api/v1/external-transfers/proposals", json=payload, headers=own)
    assert replay.json()["id"] == job_id
    assert client.get("/api/v1/external-transfers/" + job_id, headers=headers("other-synthetic")).status_code == 404
    assert client.get("/api/v1/xray/analyses/" + analysis_id + "/fhir", headers=headers("other-synthetic")).status_code == 404
    preview = client.get("/api/v1/xray/analyses/" + analysis_id + "/fhir", headers=own)
    assert preview.status_code == 200
    assert preview.json()["validation"]["full_schema_status"] == "NOT_VERIFIED"
    absent = client.post("/api/v1/external-transfers/" + job_id + "/confirm", headers=own,
        json={"confirmed": False, "reason": "Synthetic confirm"})
    assert absent.status_code == 422
    blocked = client.post("/api/v1/external-transfers/" + job_id + "/confirm", headers=own,
        json={"confirmed": True, "reason": "Synthetic confirm"})
    assert blocked.status_code == 409 and blocked.json()["transmitted"] is False
    assert "CLINICIAN_REVIEW_REQUIRED" in blocked.json()["reason_codes"]
    with SessionLocal() as db:
        events = db.scalars(select(ExternalTransferEvent).where(ExternalTransferEvent.transfer_job_id == job_id)).all()
        assert {e.event_type for e in events} == {"TRANSFER_PROPOSED", "TRANSFER_BLOCKED"}
    health = client.post("/api/v1/integrations/health-check", headers=own)
    assert health.status_code == 200
    assert all(item["status"] == "NOT_CONFIGURED" for item in health.json().values())
