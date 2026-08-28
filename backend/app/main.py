import logging, time, uuid
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.constants import REGIONS
from app.core.logging import configure_logging
from app.core.rate_limit import SlidingWindowLimiter
from app.db.database import Base, engine, get_db
from app.db.models import Prediction
from app.schemas import PredictionOut, ReviewUpdate, ValidationOut
from app.services.dicom_service import metadata_orientation
from app.services.file_validation import validate_upload
from app.services.inference import engine as inference_engine, file_digest
from app.services.policy import review_decision
from app.services.quality import assess_image_quality

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
@app.post("/api/predictions", response_model=PredictionOut)
async def predict(file: UploadFile=File(...), db: Session=Depends(get_db)):
    started=time.perf_counter(); data=await file.read(); v=validate_upload(file.filename or "",file.content_type or "",data); digest=file_digest(data)
    top=inference_engine.predict(v.pixels,digest); lat=view="UNKNOWN"; body=None
    if v.dicom is not None: lat,view,body=metadata_orientation(v.dicom)
    quality=assess_image_quality(v.pixels)
    required,reasons=review_decision(top,lat,view,body,quality.reasons)
    p=Prediction(file_hash=digest,file_format=v.format,width=v.width,height=v.height,anatomical_region=top[0]["class"],confidence=top[0]["confidence"],top_predictions=top,laterality=lat,view_position=view,review_required=required,review_reasons=reasons,model_version=settings.model_version,dummy_mode=True,processing_time_ms=max(1,int((time.perf_counter()-started)*1000)))
    db.add(p); db.commit(); db.refresh(p); return serialize(p)
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
def review(prediction_id: str, body: ReviewUpdate, db: Session=Depends(get_db)):
    if body.corrected_region not in REGIONS: raise HTTPException(422,"지원하지 않는 분류입니다.")
    p=db.get(Prediction,prediction_id)
    if not p: raise HTTPException(404,"예측 결과를 찾을 수 없습니다.")
    p.corrected_region=body.corrected_region; p.review_comment=body.comment; p.reviewed_at=datetime.now(timezone.utc); p.review_required=False; db.commit(); db.refresh(p); return serialize(p)
@app.get("/api/statistics/summary")
def stats(db: Session=Depends(get_db)):
    rows=db.execute(select(Prediction.anatomical_region,func.count(),func.avg(Prediction.confidence)).group_by(Prediction.anatomical_region)).all(); total=db.scalar(select(func.count()).select_from(Prediction)) or 0; review=db.scalar(select(func.count()).select_from(Prediction).where(Prediction.review_required==True)) or 0
    return {"total":total,"average_confidence":float(db.scalar(select(func.avg(Prediction.confidence))) or 0),"review_required_rate":review/total if total else 0,"by_region":[{"class":r[0],"count":r[1],"average_confidence":r[2]} for r in rows]}
@app.get("/api/statistics/confusion-matrix")
def confusion_matrix(): return {"available":False,"message":"검토된 정답 데이터가 충분할 때 계산됩니다.","labels":list(REGIONS),"matrix":[]}

