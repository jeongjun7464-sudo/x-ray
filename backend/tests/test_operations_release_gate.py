from io import BytesIO
import pydicom
import pytest
import uuid
from fastapi.testclient import TestClient
from pydicom.uid import generate_uid
from app.main import app,limiter
from app.services.synthetic_dicom import generate_synthetic_dicom

client=TestClient(app)
@pytest.fixture(autouse=True)
def reset():limiter._events.clear()

def dicom(study_uid,view,sop_uid=None):
    ds=pydicom.dcmread(BytesIO(generate_synthetic_dicom()));ds.StudyInstanceUID=study_uid;ds.SeriesInstanceUID=generate_uid();ds.SOPInstanceUID=sop_uid or generate_uid();ds.file_meta.MediaStorageSOPInstanceUID=ds.SOPInstanceUID;ds.ViewPosition=view;out=BytesIO();ds.save_as(out,enforce_file_format=True);return out.getvalue()
def import_study(files,context="{}",role="TECHNICIAN"):
    return client.post("/api/v1/studies/import",headers={"X-Role":role},files=[("files",(name,data,"application/dicom")) for name,data in files],data={"clinical_context_json":context})

def test_multiview_group_duplicate_block_missing_view_and_clinical_allowlist():
    uid=generate_uid();created=import_study([("ap.dcm",dicom(uid,"AP")),("lat.dcm",dicom(uid,"LATERAL"))],'{"anonymous_subject_id":"anon-1","age_group":"40-49","sex":"UNKNOWN","symptom_codes":["COUGH"]}')
    assert created.status_code==200;data=created.json();assert data["instance_count"]==2 and data["protocol"]["status"]=="COMPLETE"
    detail=client.get(f'/api/v1/studies/{data["study_id"]}').json();assert len(detail["instances"])==2 and all(len(x["sop_uid_hash"])==64 for x in detail["instances"])
    missing_uid=generate_uid();missing=import_study([("ap.dcm",dicom(missing_uid,"AP"))]);assert missing.json()["protocol"]["status"]=="MISSING_VIEW" and "LATERAL" in missing.json()["protocol"]["missing"]
    duplicate_uid=generate_uid();sop=generate_uid();duplicate=import_study([("a.dcm",dicom(duplicate_uid,"AP",sop)),("b.dcm",dicom(duplicate_uid,"LATERAL",sop))]);assert duplicate.status_code==409
    forbidden=import_study([("x.dcm",dicom(generate_uid(),"AP"))],'{"name":"patient"}');assert forbidden.status_code==422

def test_priority_rule_rbac_and_pacs_not_configured():
    uid=generate_uid();study=import_study([("ap.dcm",dicom(uid,"AP")),("lat.dcm",dicom(uid,"LATERAL"))]).json();analysis=client.post(f'/api/v1/studies/{study["study_id"]}/analyze',headers={"X-Role":"TECHNICIAN"})
    assert analysis.status_code==200 and analysis.json()["priority"]["status"] in {"ROUTINE","REVIEW_REQUIRED","HIGH_PRIORITY_REVIEW","QUALITY_REJECTED"}
    work_id=analysis.json()["analysis_id"];assert client.patch(f'/api/v1/worklist/{work_id}/priority',headers={"X-Role":"TECHNICIAN"},json={"status":"ROUTINE"}).status_code==403
    changed=client.patch(f'/api/v1/worklist/{work_id}/priority',headers={"X-Role":"RADIOLOGIST"},json={"status":"REVIEW_REQUIRED","reason":"manual review"});assert changed.status_code==200
    assert client.patch("/api/v1/worklist/rules",headers={"X-Role":"ML_ENGINEER"},json={"version":"2"}).status_code==403
    assert client.patch("/api/v1/worklist/rules",headers={"X-Role":"ADMIN"},json={"version":"test-"+uuid.uuid4().hex,"thresholds":{"high_priority_finding_probability":.9,"capa_repeat_count":3},"reason":"validated change"}).status_code==200
    status=client.get("/api/v1/integrations/status").json();assert status["pacs"]=="NOT_CONFIGURED" and status["external_transmission"]=="DISABLED_BY_DEFAULT"

def register(version,sha,rollback=None):
    body={"name":"finding-model","version":version,"model_sha256":sha,"training_dataset_version":"train-v1","test_dataset_version":"test-v1","rollback_model_id":rollback}
    return client.post("/api/v1/models/register",headers={"X-Role":"ML_ENGINEER"},json=body)
def approve(model_id):
    assert client.post(f'/api/v1/models/{model_id}/validate',headers={"X-Role":"ML_ENGINEER"},json={"required_tests_passed":True,"test_ids":["T1"],"comparison_result":{"status":"NON_INFERIOR","metrics":"NOT_DISCLOSED_TEST_FIXTURE"}}).status_code==200
    return client.post(f'/api/v1/models/{model_id}/approve',headers={"X-Role":"QA_RA"},json={"approver":"qa-reviewer","reason":"required synthetic tests passed"})

def test_unapproved_deploy_block_and_model_rollback():
    old=register("old",uuid.uuid4().hex*2).json()["model_id"];approve(old);assert client.post(f'/api/v1/models/{old}/deploy',headers={"X-Role":"ADMIN"}).status_code==200
    new=register("new",uuid.uuid4().hex*2,old).json()["model_id"];assert client.post(f'/api/v1/models/{new}/deploy',headers={"X-Role":"ADMIN"}).status_code==409
    approve(new);assert client.post(f'/api/v1/models/{new}/deploy',headers={"X-Role":"ADMIN"}).status_code==200
    rolled=client.post(f'/api/v1/models/{new}/rollback',headers={"X-Role":"ADMIN"});assert rolled.status_code==200 and rolled.json()["deployed_model_id"]==old

def test_gradcam_role_and_dummy_restriction():
    uid=generate_uid();study=import_study([("ap.dcm",dicom(uid,"AP")),("lat.dcm",dicom(uid,"LATERAL"))]).json();detail=client.get(f'/api/v1/studies/{study["study_id"]}').json();analysis_id=detail["instances"][0]["analysis_id"]
    assert client.get(f'/api/v1/xray/analyses/{analysis_id}/gradcam-viewer',headers={"X-Role":"TECHNICIAN"}).status_code==403
    result=client.get(f'/api/v1/xray/analyses/{analysis_id}/gradcam-viewer',headers={"X-Role":"RADIOLOGIST"}).json();assert result["enabled"] is False and result["status"]=="DUMMY_DISABLED" and "진단 근거" in result["warning"]

def test_repeated_error_creates_and_updates_capa_candidate():
    payload={"error_type":"REGION_MISCLASSIFICATION_"+uuid.uuid4().hex,"analysis_id":"anonymous-analysis","model_version":"dummy-v1","dataset_version":"synthetic-v1","repeat_threshold":3}
    first=client.post("/api/v1/capa",headers={"X-Role":"QA_RA"},json=payload).json();second=client.post("/api/v1/capa",headers={"X-Role":"QA_RA"},json=payload).json();third=client.post("/api/v1/capa",headers={"X-Role":"QA_RA"},json=payload).json()
    assert not first["capa_candidate"] and not second["capa_candidate"] and third["capa_candidate"]
    updated=client.patch(f'/api/v1/capa/{third["capa_id"]}',headers={"X-Role":"QA_RA"},json={"root_cause":"label mismatch","corrective_action":"review labels","preventive_action":"add regression set","owner":"qa","due_date":"2026-12-31","effectiveness_check":"pending","status":"APPROVED","approved_by":"qa-lead"})
    assert updated.status_code==200 and updated.json()["status"]=="APPROVED" and "anonymous-analysis" in updated.json()["analysis_ids"]

def test_monitoring_exposes_measured_and_unknown_values():
    data=client.get("/api/v1/monitoring/metrics").json();assert "total_analyses" in data and "p95_processing_ms" in data and data["services"]["pacs"]=="NOT_CONFIGURED"
