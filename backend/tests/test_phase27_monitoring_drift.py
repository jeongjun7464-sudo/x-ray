import uuid
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import ModelRelease,OperationalCapa
from app.main import app,limiter
from app.services.drift_monitoring import evaluate_drift

client=TestClient(app)
def metrics(a=50,b=50):return {"brightness_distribution":{"low":a,"normal":b},"contrast_distribution":{"low":a,"normal":b},"region_distribution":{"CHEST":a,"KNEE":b},"ood_rate":.05,"unknown_rate":.02,"correction_rate":.03,"quality_reject_rate":.04}

def test_drift_statuses_and_missing_measurements():
    assert evaluate_drift({}, {},0,0)["status"]=="NOT_MEASURED"
    assert evaluate_drift(metrics(),metrics(),10,10,min_samples=30)["status"]=="INSUFFICIENT_DATA"
    assert evaluate_drift(metrics(),metrics(51,49),100,100)["status"]=="STABLE"
    warning=evaluate_drift(metrics(),metrics(75,25),100,100,warning_threshold=.04,critical_threshold=.4);assert warning["status"]=="WARNING"
    critical=evaluate_drift(metrics(),metrics(100,0),100,100,warning_threshold=.04,critical_threshold=.2);assert critical["status"]=="CRITICAL" and critical["performance_claim"] is False

def test_snapshot_baseline_evaluation_alert_and_capa_candidate():
    limiter._events.clear();suffix=uuid.uuid4().hex[:8];version=f"phase27-{suffix}";dataset=f"synthetic-{suffix}"
    baseline=client.post("/api/v1/drift/baselines",headers={"X-Role":"QA_RA"},json={"model_version":version,"dataset_version":dataset,"sample_size":100,"metrics":metrics()});assert baseline.status_code==200
    snapshot=client.post("/api/v1/monitoring/snapshots",headers={"X-Role":"ML_ENGINEER"},json={"model_version":version,"dataset_version":dataset,"institution_id":"ANON-SITE","sample_size":100,"metrics":metrics(100,0)});assert snapshot.status_code==200 and snapshot.json()["status"]=="MEASURED"
    payload={"baseline_id":baseline.json()["baseline_id"],"snapshot_id":snapshot.json()["snapshot_id"],"warning_threshold":.04,"critical_threshold":.2}
    first=client.post("/api/v1/drift/evaluate",headers={"X-Role":"QA_RA"},json=payload);second=client.post("/api/v1/drift/evaluate",headers={"X-Role":"QA_RA"},json=payload);assert first.json()["status"]=="CRITICAL" and second.json()["status"]=="CRITICAL"
    alerts=client.get("/api/v1/monitoring/alerts").json();alert=next(x for x in alerts if x["evaluation_id"]==first.json()["evaluation_id"]);assert alert["severity"]=="CRITICAL"
    assert client.patch(f"/api/v1/monitoring/alerts/{alert['alert_id']}",headers={"X-Role":"QA_RA"},json={"status":"RESOLVED"}).status_code==422
    assert client.patch(f"/api/v1/monitoring/alerts/{alert['alert_id']}",headers={"X-Role":"QA_RA"},json={"status":"RESOLVED","change_reason":"합성 분포 변경 검토","assigned_role":"QA_RA"}).status_code==200
    with SessionLocal() as db:assert db.scalar(select(OperationalCapa).where(OperationalCapa.error_type=="REPEATED_CRITICAL_DATA_DRIFT",OperationalCapa.model_version==version)).status=="CANDIDATE"

def test_release_gate_blocks_critical_and_version_mismatch():
    suffix=uuid.uuid4().hex[:8];version=f"gate-{suffix}";dataset=f"gate-data-{suffix}"
    with SessionLocal() as db:
        release=ModelRelease(name="phase27",version=version,model_sha256=(suffix*8)[:64],training_dataset_version=dataset,test_dataset_version=dataset,status="APPROVED");db.add(release);db.commit();release_id=release.id
    baseline=client.post("/api/v1/drift/baselines",headers={"X-Role":"QA_RA"},json={"model_version":version,"dataset_version":dataset,"sample_size":100,"metrics":metrics()}).json();snapshot=client.post("/api/v1/monitoring/snapshots",headers={"X-Role":"ADMIN"},json={"model_version":version,"dataset_version":dataset,"sample_size":100,"metrics":metrics(100,0)}).json();client.post("/api/v1/drift/evaluate",headers={"X-Role":"QA_RA"},json={"baseline_id":baseline["baseline_id"],"snapshot_id":snapshot["snapshot_id"],"critical_threshold":.2})
    gate=client.post(f"/api/v1/releases/{release_id}/monitoring-gate",headers={"X-Role":"QA_RA"},json={"checkpoint_sha256":"b"*64,"dataset_version":"wrong"});assert gate.status_code==200 and gate.json()["blocked"] is True
    assert {"CRITICAL_DATA_DRIFT","CHECKPOINT_HASH_MISMATCH","VALIDATION_DATASET_VERSION_MISMATCH"}.issubset(gate.json()["reason_codes"]);assert gate.json()["automatic_deployment"] is False

def test_monitoring_rbac_and_authentication(monkeypatch):
    limiter._events.clear();assert client.post("/api/v1/monitoring/snapshots",headers={"X-Role":"USER"},json={}).status_code==403
    monkeypatch.setattr(settings,"auth_enforced",True);monkeypatch.setattr(settings,"auth_session_secret","a-secure-phase27-test-secret-with-adequate-entropy")
    assert client.post("/api/v1/monitoring/snapshots",json={}).status_code==401
    monkeypatch.setattr(settings,"auth_enforced",False)

def test_monitoring_consistency_rules_are_registered():
    rules=client.get("/api/v1/consistency/rules").json();ids={x["rule_id"] for x in rules};assert {f"MON-{i:03d}" for i in range(1,11)}.issubset(ids)
