from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.services.quality import assess_image_quality

client=TestClient(app)
def png_bytes():
    b=BytesIO(); Image.new("L",(64,64),128).save(b,"PNG"); return b.getvalue()
def test_health(): assert client.get("/api/health").json()["status"]=="ok"
def test_png_prediction_schema():
    r=client.post("/api/predictions",files={"file":("x.png",png_bytes(),"image/png")}); assert r.status_code==200
    data=r.json(); assert len(data["top_predictions"])==3 and data["dummy_mode"] is True and data["review_required"] is True
    assert data["preview_data_url"].startswith("data:image/png;base64,")
def test_spoofed_mime(): assert client.post("/api/images/validate",files={"file":("x.png",png_bytes(),"image/jpeg")}).status_code==400
def test_bad_extension(): assert client.post("/api/images/validate",files={"file":("x.exe",b"x","application/octet-stream")}).status_code==400
def test_quality_flags_flat_image(): assert "LOW_CONTRAST" in assess_image_quality(Image.new("L",(64,64),128)).reasons
def test_review_update():
    p=client.post("/api/predictions",files={"file":("x.jpg",_jpeg(),"image/jpeg")}).json()
    r=client.patch(f'/api/predictions/{p["prediction_id"]}/review',json={"corrected_region":"CHEST","comment":"검토 완료"}); assert r.status_code==200 and not r.json()["review_required"]
    events=client.get('/api/audit-events').json(); assert any(x['action']=='PREDICTION_REVIEWED' for x in events)
    csv_export=client.get('/api/active-learning/export.csv'); assert csv_export.status_code==200 and 'corrected_region' in csv_export.text
    report=client.get(f'/api/predictions/{p["prediction_id"]}/report.pdf'); assert report.status_code==200 and report.content.startswith(b'%PDF')
def test_synthetic_dicom_and_ood():
    normal=client.get('/api/demo/synthetic-dicom?variant=normal'); assert normal.status_code==200 and normal.headers['x-synthetic-data']=='true'
    ood=client.get('/api/demo/synthetic-dicom?variant=wrong_modality').content
    result=client.post('/api/predictions',files={'file':('synthetic.dcm',ood,'application/dicom')}).json()
    assert result['distribution_status']=='OUT_OF_DISTRIBUTION' and result['routing_target']=='REVIEW_QUEUE' and result['priority']=='HIGH'
def test_model_comparison_is_explicitly_mock():
    r=client.post('/api/model-comparison',files={'file':('x.png',png_bytes(),'image/png')}); assert r.status_code==200
    assert len(r.json()['comparison'])==4 and all(x['mock_mode'] for x in r.json()['comparison'])
def _jpeg():
    b=BytesIO(); Image.new("RGB",(64,64),"white").save(b,"JPEG"); return b.getvalue()
