import base64, csv, logging, time, uuid
from io import BytesIO
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from PIL import Image
from app.core.config import settings
from app.core.constants import REGIONS
from app.core.logging import configure_logging
from app.core.rate_limit import SlidingWindowLimiter
from app.db.database import Base, engine, get_db
from app.db.models import AuditEvent, Prediction
from app.schemas import PredictionOut, ReviewUpdate, ValidationOut
from app.services.dicom_service import metadata_orientation
from app.services.file_validation import validate_upload
from app.services.inference import engine as inference_engine, file_digest
from app.services.policy import review_decision
from app.services.quality import assess_image_quality
from app.services.audit import record_audit
from app.services.differentiators import assess_extended, mock_model_comparison
from app.services.synthetic_dicom import generate_synthetic_dicom

configure_logging()
logger = logging.getLogger("xray.api")
limiter = SlidingWindowLimiter(settings.rate_limit_per_minute)
Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.app_name, version="0.1.0", description="연구·교육용 영상 분류 API이며 진단용이 아닙니다.")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"] ,allow_headers=["*"])
@app.on_event("startup")
def startup(): Base.metadata.create_all(bind=engine)
@app.middleware("http")
async def security(request: Request, call_next):
    request_id=request.headers.get("X-Request-ID",uuid.uuid4().hex)
    client=request.client.host if request.client else "unknown"
    if request.url.path.startswith("/api/") and not limiter.allow(client):
        return JSONResponse(status_code=429,content={"error":{"code":"RATE_LIMITED","message":"요청이 너무 많습니다. 잠시 후 다시 시도하세요."}},headers={"Retry-After":"60","X-Request-ID":request_id})
    started=time.perf_counter(); response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"; response.headers["X-Frame-Options"]="DENY"; response.headers["Referrer-Policy"]="no-referrer"; response.headers["Content-Security-Policy"]="default-src 'none'; frame-ancestors 'none'"; response.headers["X-Request-ID"]=request_id
    logger.info("request_completed",extra={"request_id":request_id,"status":response.status_code,"duration_ms":int((time.perf_counter()-started)*1000)})
    return response
@app.exception_handler(ValueError)
async def bad_request(_: Request, exc: ValueError): return JSONResponse(status_code=400, content={"error":{"code":"INVALID_FILE","message":str(exc)}})
@app.get("/api/health")
def health(): return {"status":"ok","dummy_mode":settings.dummy_mode}
@app.get("/api/model/info")
def model_info(): return {"version":settings.model_version,"dummy_mode":settings.dummy_mode,"device":"cpu","disclaimer":"연구·교육용이며 진단용이 아닙니다."}
@app.get("/api/classes")
def classes(): return [{"class":k,"display_name":v} for k,v in REGIONS.items()]
@app.post("/api/images/validate", response_model=ValidationOut)
async def validate(file: UploadFile=File(...)):
    data=await file.read(); v=validate_upload(file.filename or "", file.content_type or "", data)
    return ValidationOut(valid=True,file_format=v.format,width=v.width,height=v.height,message="사용 가능한 영상입니다.")
def serialize(p: Prediction) -> PredictionOut:
    return PredictionOut(prediction_id=p.id, anatomical_region=p.anatomical_region, display_name=REGIONS[p.anatomical_region], confidence=p.confidence, top_predictions=p.top_predictions, laterality=p.laterality, view_position=p.view_position, review_required=p.review_required, review_reasons=p.review_reasons, model_version=p.model_version, dummy_mode=p.dummy_mode, processing_time_ms=p.processing_time_ms, created_at=p.created_at)

def preview_url(pixels: object) -> str:
    image = pixels if isinstance(pixels, Image.Image) else Image.fromarray(pixels)
    out = BytesIO(); image.convert("L").save(out, "PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")
@app.post("/api/predictions", response_model=PredictionOut)
async def predict(request: Request, file: UploadFile=File(...), db: Session=Depends(get_db)):
    started=time.perf_counter(); data=await file.read(); v=validate_upload(file.filename or "",file.content_type or "",data); digest=file_digest(data)
    top=inference_engine.predict(v.pixels,digest); lat=view="UNKNOWN"; body=None
    if v.dicom is not None: lat,view,body=metadata_orientation(v.dicom)
    quality=assess_image_quality(v.pixels)
    extended=assess_extended(v.pixels,top,v.dicom,quality)
    policy_quality=tuple(set(quality.reasons)|set(extended.quality_reasons)|set(extended.metadata_warnings)|({"OUT_OF_DISTRIBUTION"} if extended.distribution_status!="IN_DISTRIBUTION" else set()))
    required,reasons=review_decision(top,lat,view,body,policy_quality)
    p=Prediction(file_hash=digest,file_format=v.format,width=v.width,height=v.height,anatomical_region=top[0]["class"],confidence=top[0]["confidence"],top_predictions=top,laterality=lat,view_position=view,review_required=required,review_reasons=reasons,model_version=settings.model_version,dummy_mode=True,processing_time_ms=max(1,int((time.perf_counter()-started)*1000)))
    db.add(p); db.flush(); record_audit(db,action="PREDICTION_CREATED",target_id=p.id,request_id=request.headers.get("X-Request-ID","generated"),after={"region":p.anatomical_region,"review_required":p.review_required})
    db.commit(); db.refresh(p); result=serialize(p); result.preview_data_url=preview_url(v.pixels)
    result.quality_status=extended.quality_status;result.quality_score=extended.quality_score;result.quality_reasons=list(extended.quality_reasons);result.distribution_status=extended.distribution_status;result.metadata_status=extended.metadata_status;result.metadata_warnings=list(extended.metadata_warnings);result.routing_target=extended.routing_target;result.priority=extended.priority
    return result
@app.get("/api/predictions", response_model=list[PredictionOut])
def list_predictions(review_required: bool|None=None, db: Session=Depends(get_db)):
    q=select(Prediction).order_by(Prediction.created_at.desc()); q=q.where(Prediction.review_required==review_required) if review_required is not None else q
    return [serialize(p) for p in db.scalars(q).all()]
@app.get("/api/predictions/{prediction_id}", response_model=PredictionOut)
def get_prediction(prediction_id: str, db: Session=Depends(get_db)):
    p=db.get(Prediction,prediction_id)
    if not p: raise HTTPException(404,"예측 결과를 찾을 수 없습니다.")
    return serialize(p)
@app.patch("/api/predictions/{prediction_id}/review", response_model=PredictionOut)
def review(prediction_id: str, body: ReviewUpdate, request: Request, db: Session=Depends(get_db)):
    if body.corrected_region not in REGIONS: raise HTTPException(422,"지원하지 않는 분류입니다.")
    p=db.get(Prediction,prediction_id)
    if not p: raise HTTPException(404,"예측 결과를 찾을 수 없습니다.")
    before={"region":p.anatomical_region,"review_required":p.review_required}; p.corrected_region=body.corrected_region; p.review_comment=body.comment; p.reviewed_at=datetime.now(timezone.utc); p.review_required=False
    record_audit(db,action="PREDICTION_REVIEWED",target_id=p.id,request_id=request.headers.get("X-Request-ID","generated"),before=before,after={"corrected_region":body.corrected_region,"review_required":False},reason=body.comment,actor_role="REVIEWER")
    db.commit(); db.refresh(p); return serialize(p)
@app.get("/api/statistics/summary")
def stats(db: Session=Depends(get_db)):
    rows=db.execute(select(Prediction.anatomical_region,func.count(),func.avg(Prediction.confidence)).group_by(Prediction.anatomical_region)).all(); total=db.scalar(select(func.count()).select_from(Prediction)) or 0; review=db.scalar(select(func.count()).select_from(Prediction).where(Prediction.review_required==True)) or 0
    return {"total":total,"average_confidence":float(db.scalar(select(func.avg(Prediction.confidence))) or 0),"review_required_rate":review/total if total else 0,"by_region":[{"class":r[0],"count":r[1],"average_confidence":r[2]} for r in rows]}
@app.get("/api/statistics/confusion-matrix")
def confusion_matrix(): return {"available":False,"message":"검토된 정답 데이터가 충분할 때 계산됩니다.","labels":list(REGIONS),"matrix":[]}

@app.get("/api/audit-events")
def audit_events(limit: int=50, db: Session=Depends(get_db)):
    limit=max(1,min(limit,200)); rows=db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [{"event_id":x.id,"action":x.action,"target_id":x.target_id,"actor_role":x.actor_role,"request_id":x.request_id,"created_at":x.created_at} for x in rows]

@app.get("/api/worklist")
def worklist(reason: str|None=None, priority: str|None=None, db: Session=Depends(get_db)):
    rows=db.scalars(select(Prediction).where(Prediction.review_required==True).order_by(Prediction.created_at)).all();out=[]
    for p in rows:
        reasons=p.review_reasons or []; high=any(x in reasons for x in ("OUT_OF_DISTRIBUTION","BLUR_OR_EMPTY","METADATA_AI_CONFLICT","METADATA_CONFLICT")); item_priority="HIGH" if high else "MEDIUM"
        if reason and reason not in reasons: continue
        if priority and priority.upper()!=item_priority: continue
        out.append({"prediction":serialize(p),"priority":item_priority,"reasons":reasons})
    return out

@app.get("/api/active-learning/export.csv")
def active_learning_export(db: Session=Depends(get_db)):
    rows=db.scalars(select(Prediction).where(Prediction.corrected_region.is_not(None))).all();text=__import__('io').StringIO(newline='');w=csv.writer(text);w.writerow(["anonymous_prediction_id","predicted_region","corrected_region","confidence","review_reasons","model_version","retraining_candidate"])
    for p in rows:w.writerow([p.id,p.anatomical_region,p.corrected_region,p.confidence,"|".join(p.review_reasons or []),p.model_version,"true"])
    data=('\ufeff'+text.getvalue()).encode('utf-8');return Response(data,media_type="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=active-learning.csv"})

@app.get("/api/demo/synthetic-dicom")
def synthetic_dicom(variant: str="normal"):
    allowed={"normal","monochrome1","monochrome2","phi","no_pixel","corrupt","wrong_modality","metadata_conflict","large"}
    if variant not in allowed: raise HTTPException(422,"지원하지 않는 합성 DICOM 유형입니다.")
    data=generate_synthetic_dicom(variant);return Response(data,media_type="application/dicom",headers={"Content-Disposition":f"attachment; filename=synthetic-{variant}.dcm","X-Synthetic-Data":"true"})

@app.post("/api/model-comparison")
async def model_comparison(file: UploadFile=File(...)):
    data=await file.read();v=validate_upload(file.filename or "",file.content_type or "",data);digest=file_digest(data);top=inference_engine.predict(v.pixels,digest);return {"comparison":mock_model_comparison(digest,top),"disclaimer":"모든 비교 결과는 모의 모델이며 질환 진단 결과가 아닙니다."}

def _simple_pdf(lines: list[str]) -> bytes:
    safe=[x.encode("latin-1","replace").decode("latin-1") for x in lines];stream="BT /F1 11 Tf 50 790 Td "+" ".join(f"({x.replace('(','[').replace(')',']')}) Tj 0 -18 Td" for x in safe)+" ET";objects=["1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj","2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj","3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj","4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",f"5 0 obj << /Length {len(stream)} >> stream\n{stream}\nendstream endobj"];pdf="%PDF-1.4\n";offsets=[0]
    for o in objects:offsets.append(len(pdf.encode()));pdf+=o+"\n"
    xref=len(pdf.encode());pdf+=f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n"+"".join(f"{x:010d} 00000 n \n" for x in offsets[1:])+f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF";return pdf.encode("latin-1")

@app.get("/api/predictions/{prediction_id}/report.pdf")
def prediction_report(prediction_id: str,db: Session=Depends(get_db)):
    p=db.get(Prediction,prediction_id)
    if not p: raise HTTPException(404,"예측 결과를 찾을 수 없습니다.")
    lines=["X-Ray Anatomical Region Classification Report",f"Anonymous analysis ID: {p.id}",f"Region: {p.anatomical_region}",f"Confidence: {p.confidence:.4f}",f"Laterality / View: {p.laterality} / {p.view_position}",f"Model: {p.model_version}",f"Processing: {p.processing_time_ms} ms",f"Review reasons: {', '.join(p.review_reasons or [])}",f"Corrected region: {p.corrected_region or 'Not reviewed'}","Research and education only. Not a medical diagnosis."]
    return Response(_simple_pdf(lines),media_type="application/pdf",headers={"Content-Disposition":f"attachment; filename={p.id}.pdf"})
