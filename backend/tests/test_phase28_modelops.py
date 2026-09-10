import uuid
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from app.main import app,limiter
from app.db.database import SessionLocal
from app.db.models import ConsistencyValidationRun,DatasetVersion,ModelRelease,ReleaseBlockDecision
from app.services.dataset_lineage_validation import validate_lineage
from app.services.model_artifact_validation import validate_artifact
from app.services.model_validation_runner import evaluate_metrics

client=TestClient(app)
def setup_data():
    suffix=uuid.uuid4().hex[:8]
    train_version=f"train-{suffix}";test_version=f"test-{suffix}"
    with SessionLocal() as db:
        train=DatasetVersion(name="synthetic-train",version=train_version,status="APPROVED",manifest=[{"image_sha256":"a"*64,"subject_hash":"s1","label_status":"APPROVED"}]);test=DatasetVersion(name="synthetic-test",version=test_version,status="APPROVED",manifest=[{"image_sha256":"b"*64,"subject_hash":"s2","label_status":"APPROVED"}]);db.add_all([train,test]);db.commit()
    return suffix,train_version,test_version
def payload(suffix,train,test):return {"name":f"safe-{suffix}","version":"1.0.0","architecture":"DenseNet121","framework":"PyTorch","model_format":"ONNX","training_dataset_version":train,"test_dataset_version":test,"intended_use":"합성 영상 부위 분류 검증","prohibited_use":"질병 진단 및 단독 임상 판단","input_specification":{"shape":[1,1,224,224]},"output_specification":{"labels":8},"preprocessing_version":"prep-1","threshold_version":"thr-1"}
def test_artifact_and_lineage_safety_services():
    assert validate_artifact("bad.exe",b"x")["status"]=="FAILED"
    assert "CHECKPOINT_HASH_MISMATCH" in validate_artifact("m.onnx",b"\x08x","0"*64)["reason_codes"]
    leak=validate_lineage({"manifest":[{"image_sha256":"x","subject_hash":"s"}]},{"manifest":[{"image_sha256":"x","subject_hash":"s"}]});assert leak["status"]=="FAILED" and "DATA_LEAKAGE_DETECTED" in leak["reason_codes"]
    assert evaluate_metrics([{"metric_name":"accuracy","value":None,"sample_size":0}],{"accuracy":.8},30)[0]["status"]=="NOT_MEASURED"
def test_registration_duplicate_artifact_policy_and_validation_flow(monkeypatch):
    # Explicit test doubles exercise orchestration only, never model validation.
    import app.phase28_router as router
    original=router.validate_artifact
    def verified_test_double(*args,**kwargs):
        result=original(*args,**kwargs)
        if result.get("signature_status")=="PREFIX_ONLY":result["status"]="VERIFIED"
        return result
    monkeypatch.setattr(router,"validate_artifact",verified_test_double)
    monkeypatch.setattr(router,"require_validation_adapter",lambda:None)
    limiter._events.clear();suffix,train,test=setup_data();body=payload(suffix,train,test);h={"X-Role":"ML_ENGINEER","X-Actor":"engineer-a"}
    created=client.post("/api/v1/model-releases",headers=h,json=body);assert created.status_code==201 and created.json()["status"]=="REGISTERED";release_id=created.json()["model_release_id"]
    assert client.post("/api/v1/model-releases",headers=h,json=body).status_code==409
    assert client.post(f"/api/v1/model-releases/{release_id}/artifact",headers=h,files={"file":("unsafe.exe",b"x","application/octet-stream")}).status_code==422
    artifact_bytes=b"\x08\x01synthetic-"+suffix.encode();artifact=client.post(f"/api/v1/model-releases/{release_id}/artifact",headers=h,files={"file":("model.onnx",artifact_bytes,"application/octet-stream")});assert artifact.status_code==200 and artifact.json()["status"]=="VERIFIED"
    assert client.post(f"/api/v1/model-releases/{release_id}/validate",headers={**h,"Idempotency-Key":f"before-policy-{suffix}"},json={"policy_id":str(uuid.uuid4())}).status_code==409
    policy=client.post("/api/v1/validation-policies",headers=h,json={"policy_id":f"p-{suffix}","version":"1","metric_thresholds":{"accuracy":.8},"minimum_sample_size":2}).json();policy_id=policy["id"]
    assert client.patch(f"/api/v1/validation-policies/{policy_id}",headers={"X-Role":"QA_RA","X-Actor":"engineer-a"},json={}).status_code==409
    assert client.patch(f"/api/v1/validation-policies/{policy_id}",headers={"X-Role":"QA_RA","X-Actor":"qa-a"},json={}).status_code==200
    assert client.patch(f"/api/v1/validation-policies/{policy_id}",headers={"X-Role":"ADMIN","X-Actor":"admin-a"},json={"active":True}).status_code==200
    validate_headers={**h,"Idempotency-Key":f"key-{suffix}"};validation=client.post(f"/api/v1/model-releases/{release_id}/validate",headers=validate_headers,json={"measurements":[{"metric_name":"accuracy","value":.9,"sample_size":2}]});assert validation.status_code==201 and validation.json()["model_status"]=="APPROVAL_REQUIRED";run_id=validation.json()["validation_run_id"]
    replay=client.post(f"/api/v1/model-releases/{release_id}/validate",headers=validate_headers,json={});assert replay.status_code==201 and replay.json()["idempotent_replay"] is True
    with SessionLocal() as db:
        consistency=ConsistencyValidationRun(scope="MODEL_OPS",target_type="MODEL_RELEASE",target_id=release_id,rule_engine_version="1.0",summary={"PASS":16},high_risk_block=False);db.add(consistency);db.commit();consistency_id=consistency.id
    same=client.post(f"/api/v1/model-releases/{release_id}/approve",headers={"X-Role":"QA_RA","X-Actor":"engineer-a"},json={"reason":"검증 근거 확인","validation_run_id":run_id,"consistency_run_id":consistency_id});assert same.status_code==409
    approved=client.post(f"/api/v1/model-releases/{release_id}/approve",headers={"X-Role":"QA_RA","X-Actor":"qa-a"},json={"reason":"합성 검증 근거 확인","validation_run_id":run_id,"consistency_run_id":consistency_id});assert approved.status_code==200 and approved.json()["regulatory_approval"] is False
    assert client.post(f"/api/v1/model-releases/{release_id}/deploy",headers={"X-Role":"USER"},json={}).status_code==403
    assert client.post(f"/api/v1/model-releases/{release_id}/deploy",headers={"X-Role":"ADMIN","X-Actor":"qa-a"},json={}).status_code==409
def test_modelops_rules_registered_and_unauthenticated_boundary(monkeypatch):
    ids={x["rule_id"] for x in client.get("/api/v1/consistency/rules").json()};assert {f"MODEL-OPS-{i:03d}" for i in range(1,17)}.issubset(ids)
    from app.core.config import settings
    monkeypatch.setattr(settings,"auth_enforced",True);monkeypatch.setattr(settings,"auth_session_secret","phase28-secure-session-secret-at-least-32-chars")
    assert client.post("/api/v1/model-releases",json={}).status_code==401
    monkeypatch.setattr(settings,"auth_enforced",False)

def test_unconfigured_verifier_cannot_accept_client_claimed_performance():
    limiter._events.clear()
    assert validate_artifact("fake.onnx",b"\x08fake")["status"]=="NOT_VERIFIABLE"
    for action,role in (("validate","ML_ENGINEER"),("approve","QA_RA"),("deploy","ADMIN")):
        response=client.post(f"/api/v1/model-releases/untrusted/{action}",headers={"X-Role":role},json={"measurements":[{"metric_name":"accuracy","value":1,"sample_size":10000}]})
        assert response.status_code==409
        assert "VALIDATION_RUNNER_NOT_CONFIGURED" in response.text
