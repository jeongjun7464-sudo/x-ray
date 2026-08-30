import hashlib
from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.services.synthetic_dicom import generate_synthetic_dicom

client=TestClient(app);ADMIN={"X-Role":"ADMIN","X-Actor":"qa-admin"}

def png():
    out=BytesIO();Image.new("L",(96,96),110).save(out,"PNG");return out.getvalue()

def test_multistage_pipeline_stops_when_xray_not_confirmed():
    p=client.post("/api/predictions",files={"file":("unknown.png",png(),"image/png")});assert p.status_code==200
    run=client.get(f'/api/pipeline-runs/{p.json()["pipeline_run_id"]}').json()
    assert run["status"]=="STOPPED" and run["stages"][0]["stage"]=="XRAY_GATE"

def test_multistage_dicom_and_safe_unavailable_models():
    client.patch("/api/admin/feature-flags/ENABLE_DETECTION",headers=ADMIN,json={"enabled":False})
    p=client.post("/api/predictions",files={"file":("synthetic.dcm",generate_synthetic_dicom(),"application/dicom")});assert p.status_code==200
    assert p.json()["pipeline_stages"][-1]["stage"]=="ROUTING"
    detection=client.get(f'/api/predictions/{p.json()["prediction_id"]}/detection').json();assert detection["status"]=="NOT_AVAILABLE" and detection["detections"]==[]
    landmarks=client.get(f'/api/predictions/{p.json()["prediction_id"]}/landmarks').json();assert landmarks["status"]=="LABELING_REQUIRED" and landmarks["predictions"]==[]

def test_preprocessing_stress_reproducibility_and_hub():
    prep=client.post("/api/research/preprocessing-comparison",files={"file":("x.png",png(),"image/png")});assert prep.status_code==200 and len(prep.json()["variants"])==4
    stress=client.post("/api/research/stress-test",files={"file":("x.png",png(),"image/png")});assert stress.status_code==200 and not stress.json()["model_performance_evaluated"]
    repro=client.get("/api/research/reproducibility?dataset_version=synthetic-v1&seed=7").json();assert repro["random_seed"]==7 and "--seed 7" in repro["rerun_command"]
    assert client.post("/api/imaging-hub/route",json={"modality":"MR","study_id":"anonymous","series_id":"anonymous"}).json()["route"]=="MRI_ADAPTER"

def test_feature_flag_double_review_and_capa():
    assert client.get("/api/admin/feature-flags").status_code==403
    flags=client.get("/api/admin/feature-flags",headers=ADMIN);assert flags.status_code==200
    changed=client.patch("/api/admin/feature-flags/ENABLE_DETECTION",headers=ADMIN,json={"enabled":True});assert changed.status_code==200 and changed.json()["enabled"]
    digest=hashlib.sha256(b"synthetic-label-only").hexdigest();task=client.post("/api/label-tasks",headers=ADMIN,json={"image_hash":digest,"assignee":"reviewer-a"}).json()["task_id"]
    first=client.post(f"/api/label-tasks/{task}/reviews",headers={"X-Role":"REVIEWER","X-Actor":"reviewer-a"},json={"labels":{"region":"CHEST"}});assert first.json()["status"]=="FIRST_REVIEWED"
    second=client.post(f"/api/label-tasks/{task}/reviews",headers={"X-Role":"REVIEWER","X-Actor":"reviewer-b"},json={"labels":{"region":"KNEE"}});assert second.json()["status"]=="DISAGREEMENT"
    final=client.post(f"/api/label-tasks/{task}/adjudicate",headers=ADMIN,json={"labels":{"region":"CHEST"},"comment":"합의 완료"});assert final.json()["status"]=="APPROVED"
    defect=client.post("/api/defects",headers=ADMIN,json={"title":"Synthetic regression","severity":"MAJOR","reproduction_steps":"Run synthetic flow","expected_result":"PASS","actual_result":"FAIL","affected_version":"0.3.0"});assert defect.status_code==200
    capa=client.post("/api/capas",headers=ADMIN,json={"defect_id":defect.json()["defect_id"],"root_cause":"test cause","corrective_action":"add guard","preventive_action":"add regression test"});assert capa.status_code==200 and capa.json()["capa_id"].startswith("CAPA-XR-")
