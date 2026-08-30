from io import BytesIO
import zipfile
import pydicom
from fastapi.testclient import TestClient
from app.main import app
from app.services.synthetic_dicom import generate_synthetic_dicom

client=TestClient(app)
ADMIN={"X-Role":"ADMIN"}

def dicom_view(view: str, study_uid: str | None=None):
    ds=pydicom.dcmread(BytesIO(generate_synthetic_dicom("normal")))
    ds.ViewPosition=view
    if study_uid: ds.StudyInstanceUID=study_uid
    out=BytesIO();ds.save_as(out,enforce_file_format=True);return out.getvalue(),str(ds.StudyInstanceUID)

def test_group_protocol_and_duplicate():
    ap,uid=dicom_view("AP");lat,_=dicom_view("LATERAL",uid)
    r=client.post("/api/studies/group",files=[("files",("ap.dcm",ap,"application/dicom")),("files",("lat.dcm",lat,"application/dicom"))])
    assert r.status_code==200 and r.json()["studies"][0]["instance_count"]==2
    assert r.json()["studies"][0]["protocol"]["status"]=="COMPLETE"
    dup=client.post("/api/studies/group",files={"files":("ap.dcm",ap,"application/dicom")})
    assert dup.status_code==200 and dup.json()["duplicates"]==["ap.dcm"]

def test_admin_rbac_protocol_mapping_and_rule():
    assert client.get("/api/admin/dashboard").status_code==403
    assert client.get("/api/admin/dashboard",headers=ADMIN).status_code==200
    p=client.put("/api/admin/protocols/KNEE",headers=ADMIN,json={"region":"KNEE","required_views":["AP","LATERAL"],"version":"2.0"});assert p.status_code==200
    mapping=client.put("/api/admin/code-mappings/CHEST",headers=ADMIN,json={"internal_code":"CHEST","korean_name":"흉부","english_name":"Chest","version":"1.0"});assert mapping.status_code==200
    rule=client.post("/api/admin/routing-rules",headers=ADMIN,json={"name":"high confidence chest","priority":10,"conditions":{"region":"CHEST","confidence_gte":0.9},"destination":"CHEST_PIPELINE","version":"1.0"});assert rule.status_code==200
    routed=client.post("/api/routing/evaluate",json={"region":"CHEST","confidence":0.95});assert routed.json()["destination"]=="CHEST_PIPELINE"

def test_fhir_sr_and_uncertainty():
    p=client.post("/api/predictions",files={"file":("x.png",_png(),"image/png")}).json()
    fhir=client.get(f'/api/predictions/{p["prediction_id"]}/fhir');assert fhir.status_code==200 and fhir.json()["resourceType"]=="Bundle"
    sr=client.get(f'/api/predictions/{p["prediction_id"]}/dicom-sr');assert sr.status_code==200 and sr.headers["x-clinical-validation"]=="UNVERIFIED"
    u=client.post("/api/uncertainty",json=[0.8,0.15,0.05]);assert u.status_code==200 and u.json()["probability_margin"]>0.6

def test_safe_zip_inspection():
    good=BytesIO()
    with zipfile.ZipFile(good,"w") as z:z.writestr("images/x.dcm",b"test")
    r=client.post("/api/batches/inspect",files={"file":("batch.zip",good.getvalue(),"application/zip")});assert r.status_code==200 and r.json()["success"]==1
    bad=BytesIO()
    with zipfile.ZipFile(bad,"w") as z:z.writestr("../escape.dcm",b"test")
    assert client.post("/api/batches/inspect",files={"file":("bad.zip",bad.getvalue(),"application/zip")}).status_code==400

def _png():
    from PIL import Image
    out=BytesIO();Image.new("L",(64,64),128).save(out,"PNG");return out.getvalue()
