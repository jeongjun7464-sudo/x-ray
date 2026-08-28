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
def _jpeg():
    b=BytesIO(); Image.new("RGB",(64,64),"white").save(b,"JPEG"); return b.getvalue()

