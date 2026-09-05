from io import BytesIO
from PIL import Image
import pytest
from fastapi.testclient import TestClient
from app.main import app,limiter

client=TestClient(app)
@pytest.fixture(autouse=True)
def reset_limiter():limiter._events.clear()
def png(value=128):
    out=BytesIO();Image.new("L",(64,64),value).save(out,"PNG");return out.getvalue()

def test_integrated_png_schema_reproducibility_and_heatmap_block():
    first=client.post("/api/v1/xray/analyze",files={"file":("x.png",png(),"image/png")});second=client.post("/api/v1/xray/analyze",files={"file":("x.png",png(),"image/png")})
    assert first.status_code==200;data=first.json();assert len(data["findings"])==10 and data["model"]["dummy_mode"]
    assert data["findings"]==second.json()["findings"] and data["explanation"]["available"] is False
    heatmap=client.get(f'/api/v1/xray/analyses/{data["analysis_id"]}/heatmap');assert heatmap.status_code==404 and "DUMMY" in heatmap.json()["detail"]
    assert client.get(f'/api/v1/xray/analyses/{data["analysis_id"]}/report').content.startswith(b"%PDF")

def test_quality_review_get_and_clinical_review_audit():
    data=client.post("/api/v1/xray/analyze",files={"file":("flat.png",png(),"image/png")}).json();assert data["routing"]["review_required"]
    assert client.get(f'/api/v1/xray/analyses/{data["analysis_id"]}').status_code==200
    reviewed=client.patch(f'/api/v1/xray/analyses/{data["analysis_id"]}/review',headers={"X-Role":"REVIEWER"},json={"final_region":"CHEST","final_findings":["LUNG_OPACITY"],"comment":"synthetic review"})
    assert reviewed.status_code==200 and reviewed.json()["reviewed"]
    assert any(x["action"]=="XRAY_ANALYSIS_REVIEWED" for x in client.get("/api/audit-events").json())

def test_corrupt_file_and_batch_limit():
    assert client.post("/api/v1/xray/analyze",files={"file":("broken.png",b"bad","image/png")}).status_code==400
    files=[("files",(f"{i}.png",png(i),"image/png")) for i in range(21)]
    assert client.post("/api/v1/xray/analyze-batch",files=files).status_code==413
