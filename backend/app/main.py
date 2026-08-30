import base64, csv, logging, time, uuid
from io import BytesIO
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
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
from app.db.models import AuditEvent, Capa, CodeMapping, Defect, FeatureFlag, IntegrationEvent, LabelTask, LineageEvent, Notification, PipelineRun, Prediction, ProtocolDefinition, RoutingRule, Study, StudyInstance
from app.schemas import CodeMappingIn, PredictionOut, ProtocolIn, ReviewUpdate, RoutingRuleIn, StudyTagsIn, ValidationOut
from app.services.dicom_service import metadata_orientation
from app.services.file_validation import validate_upload
from app.services.inference import engine as inference_engine, file_digest
from app.services.policy import review_decision
from app.services.quality import assess_image_quality
from app.services.audit import record_audit
from app.services.differentiators import assess_extended, mock_model_comparison
from app.services.synthetic_dicom import generate_synthetic_dicom
from app.services.institution import apply_rules, dicom_group_metadata, experimental_sr, fhir_bundle, generated_tags, inspect_zip, protocol_check, uncertainty, webhook_signature
from app.services.advanced_ai import detection_interface, landmark_interface, preprocessing_comparison, reproducibility_manifest, run_multistage, stress_test

configure_logging()
logger = logging.getLogger("xray.api")
limiter = SlidingWindowLimiter(settings.rate_limit_per_minute)
Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.app_name, version="0.1.0", description="연구·교육용 영상 분류 API이며 진단용이 아닙니다.")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"] ,allow_headers=["*"])
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    with next(get_db()) as db:
        defaults={"CHEST":(["PA","AP"],["LATERAL"]),"KNEE":(["AP","LATERAL"],[]),"HAND_WRIST":(["PA","OBLIQUE","LATERAL"],[]),"ANKLE":(["AP","MORTISE","LATERAL"],[]),"CERVICAL_SPINE":(["AP","LATERAL"],[])}
        for region,(required,optional) in defaults.items():
            if not db.scalar(select(ProtocolDefinition).where(ProtocolDefinition.region==region)): db.add(ProtocolDefinition(region=region,required_views=required,optional_views=optional))
        for key in ("ENABLE_DICOM_SR","ENABLE_FHIR","ENABLE_OCR","ENABLE_DETECTION","ENABLE_ENSEMBLE","ENABLE_SHADOW_MODEL","ENABLE_DRIFT_MONITORING","ENABLE_REPORT_EXPORT"):
            if not db.get(FeatureFlag,key): db.add(FeatureFlag(key=key,enabled=key in {"ENABLE_DICOM_SR","ENABLE_FHIR","ENABLE_REPORT_EXPORT"}))
        db.commit()
startup()

def require_role(role: str | None, allowed: set[str]):
    current=(role or "USER").upper()
    if current not in allowed: raise HTTPException(403,"이 작업을 수행할 권한이 없습니다.")
    return current
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
    pipeline=run_multistage(v,top,digest,lat,view,body); run=PipelineRun(input_hash=digest,status=pipeline["status"],final_route=pipeline["final_route"],stages=pipeline["stages"])
    db.add(p); db.add(run); db.flush(); db.add(LineageEvent(asset_hash=digest,stage="PREDICTION",input_hash=digest,output_hash=file_digest(str(top).encode()),code_version=settings.code_version,config_version="runtime-v1",success=True)); db.add(Notification(event_type="prediction.review_required" if required else "prediction.completed",message="분석 결과가 검토 대기열에 등록되었습니다." if required else "분석이 완료되었습니다.",severity="WARNING" if required else "INFO")); record_audit(db,action="PREDICTION_CREATED",target_id=p.id,request_id=request.headers.get("X-Request-ID","generated"),after={"region":p.anatomical_region,"review_required":p.review_required,"pipeline_run_id":run.id})
    db.commit(); db.refresh(p); result=serialize(p); result.preview_data_url=preview_url(v.pixels)
    result.quality_status=extended.quality_status;result.quality_score=extended.quality_score;result.quality_reasons=list(extended.quality_reasons);result.distribution_status=extended.distribution_status;result.metadata_status=extended.metadata_status;result.metadata_warnings=list(extended.metadata_warnings);result.routing_target=extended.routing_target;result.priority=extended.priority
    result.pipeline_run_id=run.id;result.pipeline_stages=run.stages
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

# Institution integration APIs are local/synthetic by default. They never transmit patient data.
@app.post("/api/studies/group")
async def group_study(request: Request, files: list[UploadFile]=File(...), db: Session=Depends(get_db)):
    if not 1 <= len(files) <= 50: raise HTTPException(422,"한 번에 1~50개 파일만 처리할 수 있습니다.")
    grouped: dict[str,dict] = {}; duplicates=[]; failures=[]
    for file in files:
        try:
            data=await file.read(); meta=dicom_group_metadata(data)
            if db.scalar(select(StudyInstance).where(StudyInstance.sop_uid_hash==meta["sop_uid_hash"])): duplicates.append(file.filename); continue
            group=grouped.setdefault(meta["study_uid_hash"],{"meta":meta,"instances":[]}); group["instances"].append(meta)
        except Exception: failures.append({"file":file.filename,"reason":"INVALID_DICOM"})
    output=[]
    for uid,group in grouped.items():
        meta=group["meta"]; region={"HAND":"HAND_WRIST","WRIST":"HAND_WRIST","CSPINE":"CERVICAL_SPINE"}.get(meta["body_part"],meta["body_part"])
        protocol=db.scalar(select(ProtocolDefinition).where(ProtocolDefinition.region==region,ProtocolDefinition.active==True)); views=[x["view_position"] for x in group["instances"]]
        checked=protocol_check(region,views,protocol.required_views if protocol else [],protocol.optional_views if protocol else [],region=="CHEST")
        study=Study(study_uid_hash=uid,anonymous_accession=meta["anonymous_accession"],study_date=meta["study_date"],region=region,protocol_status=checked["status"],views=views,tags=generated_tags(region,views[0] if views else "UNKNOWN",meta["laterality"],"UNKNOWN",settings.model_version)); db.add(study); db.flush()
        for item in group["instances"]: db.add(StudyInstance(study_id=study.id,series_uid_hash=item["series_uid_hash"],sop_uid_hash=item["sop_uid_hash"],series_number=item["series_number"],instance_number=item["instance_number"],view_position=item["view_position"],laterality=item["laterality"]))
        output.append({"study_id":study.id,"region":region,"instance_count":len(group["instances"]),"views":views,"protocol":checked,"tags":study.tags})
    record_audit(db,action="STUDIES_GROUPED",request_id=request.headers.get("X-Request-ID","generated"),after={"studies":len(output),"duplicates":len(duplicates),"failures":len(failures)}); db.commit()
    return {"studies":output,"duplicates":duplicates,"failures":failures}

@app.get("/api/studies")
def studies(db: Session=Depends(get_db)):
    return [{"study_id":x.id,"region":x.region,"views":x.views,"protocol_status":x.protocol_status,"tags":x.tags,"created_at":x.created_at} for x in db.scalars(select(Study).order_by(Study.created_at.desc())).all()]

@app.patch("/api/studies/{study_id}/tags")
def update_study_tags(study_id: str, body: StudyTagsIn, request: Request, x_role: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN","REVIEWER"}); study=db.get(Study,study_id)
    if not study: raise HTTPException(404,"검사를 찾을 수 없습니다.")
    before=study.tags; study.tags=body.tags; record_audit(db,action="STUDY_TAGS_UPDATED",target_id=study.id,request_id=request.headers.get("X-Request-ID","generated"),before={"tags":before},after={"tags":body.tags},actor_role=(x_role or "REVIEWER").upper()); db.commit(); return {"study_id":study.id,"tags":study.tags}

@app.get("/api/admin/protocols")
def protocols(db: Session=Depends(get_db)):
    return [{"id":x.id,"region":x.region,"required_views":x.required_views,"optional_views":x.optional_views,"active":x.active,"version":x.version} for x in db.scalars(select(ProtocolDefinition)).all()]

@app.put("/api/admin/protocols/{region}")
def put_protocol(region: str, body: ProtocolIn, request: Request, x_role: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"}); row=db.scalar(select(ProtocolDefinition).where(ProtocolDefinition.region==region.upper())) or ProtocolDefinition(region=region.upper()); before={"required_views":row.required_views,"optional_views":row.optional_views} if row.id else None
    row.required_views=[x.upper() for x in body.required_views]; row.optional_views=[x.upper() for x in body.optional_views]; row.active=body.active; row.version=body.version; db.add(row); db.flush(); record_audit(db,action="PROTOCOL_UPDATED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),before=before,after={"region":row.region,"version":row.version},actor_role="ADMIN"); db.commit(); return {"id":row.id,"region":row.region,"version":row.version}

@app.get("/api/admin/code-mappings")
def code_mappings(db: Session=Depends(get_db)):
    return [{c.name:getattr(x,c.name) for c in CodeMapping.__table__.columns} for x in db.scalars(select(CodeMapping)).all()]

@app.put("/api/admin/code-mappings/{internal_code}")
def put_code_mapping(internal_code: str, body: CodeMappingIn, request: Request, x_role: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"}); row=db.scalar(select(CodeMapping).where(CodeMapping.internal_code==internal_code.upper())) or CodeMapping(internal_code=internal_code.upper(),korean_name=body.korean_name,english_name=body.english_name)
    before={"snomed_ct":row.snomed_ct,"radlex":row.radlex}; row.korean_name=body.korean_name;row.english_name=body.english_name;row.snomed_ct=body.snomed_ct;row.radlex=body.radlex;row.dicom_body_part=body.dicom_body_part;row.active=body.active;row.version=body.version;db.add(row);db.flush();record_audit(db,action="CODE_MAPPING_UPDATED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),before=before,after={"internal_code":row.internal_code,"version":row.version},actor_role="ADMIN");db.commit();return {"id":row.id,"internal_code":row.internal_code,"notice":"검증된 표준 코드만 관리자가 입력해야 합니다."}

@app.get("/api/predictions/{prediction_id}/fhir")
def prediction_fhir(prediction_id: str, db: Session=Depends(get_db)):
    p=db.get(Prediction,prediction_id)
    if not p: raise HTTPException(404,"예측 결과를 찾을 수 없습니다.")
    return fhir_bundle(p)

@app.get("/api/predictions/{prediction_id}/dicom-sr")
def prediction_sr(prediction_id: str, db: Session=Depends(get_db)):
    p=db.get(Prediction,prediction_id)
    if not p: raise HTTPException(404,"예측 결과를 찾을 수 없습니다.")
    return Response(experimental_sr(p),media_type="application/dicom",headers={"Content-Disposition":f"attachment; filename={p.id}-experimental-sr.dcm","X-Clinical-Validation":"UNVERIFIED"})

@app.get("/api/admin/routing-rules")
def routing_rules(db: Session=Depends(get_db)):
    return [{c.name:getattr(x,c.name) for c in RoutingRule.__table__.columns} for x in db.scalars(select(RoutingRule).order_by(RoutingRule.priority)).all()]

@app.post("/api/admin/routing-rules")
def create_rule(body: RoutingRuleIn, request: Request, x_role: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"}); row=RoutingRule(**body.model_dump());db.add(row);db.flush();record_audit(db,action="ROUTING_RULE_CREATED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after=body.model_dump(),actor_role="ADMIN");db.commit();return {"id":row.id,"version":row.version}

@app.post("/api/routing/evaluate")
def evaluate_routing(context: dict, db: Session=Depends(get_db)):
    rules=db.scalars(select(RoutingRule).where(RoutingRule.active==True)).all(); return apply_rules(context,rules)

@app.post("/api/batches/inspect")
async def batch_inspect(file: UploadFile=File(...)):
    if not (file.filename or "").lower().endswith(".zip"): raise HTTPException(422,"ZIP 파일만 배치 검사할 수 있습니다.")
    files=inspect_zip(await file.read()); accepted=sum(x["accepted"] for x in files)
    return {"total":len(files),"success":accepted,"failed":len(files)-accepted,"duplicates":0,"review_required":0,"progress":100,"estimated_seconds_remaining":0,"files":files}

@app.post("/api/webhooks/events")
def queue_webhook(event_type: str, request: Request, x_role: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"}); allowed={"prediction.completed","prediction.review_required","prediction.reviewed","quality.rejected","model.changed"}
    if event_type not in allowed: raise HTTPException(422,"지원하지 않는 웹훅 이벤트입니다.")
    payload={"event":event_type,"synthetic":True,"created_at":datetime.now(timezone.utc).isoformat()}; timestamp=int(time.time()); secret=settings.webhook_secret if hasattr(settings,"webhook_secret") else "development-only"
    row=IntegrationEvent(event_type=event_type,payload=payload,status="PENDING");db.add(row);db.flush();record_audit(db,action="WEBHOOK_QUEUED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"event_type":event_type},actor_role="ADMIN");db.commit();return {"event_id":row.id,"status":"PENDING","timestamp":timestamp,"signature":webhook_signature(payload,timestamp,secret),"delivery":"LOCAL_QUEUE_ONLY"}

@app.get("/api/admin/dashboard")
def admin_dashboard(x_role: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"}); total=db.scalar(select(func.count()).select_from(Prediction)) or 0; review=db.scalar(select(func.count()).select_from(Prediction).where(Prediction.review_required==True)) or 0; avg=float(db.scalar(select(func.avg(Prediction.processing_time_ms))) or 0)
    return {"services":{"api":"UP","database":"UP","model":"DUMMY_READY","queue":"LOCAL","orthanc":"NOT_CONFIGURED","minio":"NOT_CONFIGURED"},"review_pending":review,"total_processed":total,"average_processing_ms":avg,"recent_errors":[],"deployment_version":app.version,"storage":{"status":"NOT_MEASURED","reason":"portable demo environment"}}

@app.post("/api/uncertainty")
def quantify_uncertainty(probabilities: list[float]):
    if not probabilities or any(x<0 or x>1 for x in probabilities): raise HTTPException(422,"0~1 확률 배열이 필요합니다.")
    return uncertainty(probabilities)

@app.get("/api/pipeline-runs/{run_id}")
def pipeline_run(run_id: str, db: Session=Depends(get_db)):
    row=db.get(PipelineRun,run_id)
    if not row: raise HTTPException(404,"파이프라인 실행을 찾을 수 없습니다.")
    return {"run_id":row.id,"input_hash":row.input_hash,"status":row.status,"final_route":row.final_route,"stages":row.stages,"created_at":row.created_at}

@app.post("/api/research/preprocessing-comparison")
async def compare_preprocessing(file: UploadFile=File(...)):
    data=await file.read();v=validate_upload(file.filename or "",file.content_type or "",data)
    return {"input_hash":file_digest(data),"variants":preprocessing_comparison(v.pixels),"selection_policy":"검증 세트에서만 비교하며 테스트 세트에 맞춰 선택하지 않습니다."}

@app.post("/api/research/stress-test")
async def run_stress_test(file: UploadFile=File(...)):
    data=await file.read();v=validate_upload(file.filename or "",file.content_type or "",data);return stress_test(v.pixels)

@app.get("/api/research/reproducibility")
def reproducibility(dataset_version: str="UNSPECIFIED", seed: int=42): return reproducibility_manifest(dataset_version,seed)

@app.get("/api/predictions/{prediction_id}/detection")
def detection(prediction_id: str, db: Session=Depends(get_db)):
    p=db.get(Prediction,prediction_id)
    if not p: raise HTTPException(404,"예측 결과를 찾을 수 없습니다.")
    flag=db.get(FeatureFlag,"ENABLE_DETECTION");return detection_interface(p.width,p.height,bool(flag and flag.enabled))

@app.get("/api/predictions/{prediction_id}/landmarks")
def landmarks(prediction_id: str, db: Session=Depends(get_db)):
    p=db.get(Prediction,prediction_id)
    if not p: raise HTTPException(404,"예측 결과를 찾을 수 없습니다.")
    return landmark_interface(p.anatomical_region)

@app.get("/api/predictions/{prediction_id}/ocr-review")
def ocr_review(prediction_id: str, db: Session=Depends(get_db)):
    if not db.get(Prediction,prediction_id): raise HTTPException(404,"예측 결과를 찾을 수 없습니다.")
    flag=db.get(FeatureFlag,"ENABLE_OCR")
    return {"status":"MODEL_NOT_CONFIGURED" if flag and flag.enabled else "DISABLED","regions":[],"mask_applied":False,"review_required":bool(flag and flag.enabled),"reason":"검증된 OCR 모델이 없어 픽셀 개인정보나 L/R 마커를 임의 판정하지 않습니다."}

@app.get("/api/admin/feature-flags")
def feature_flags(x_role: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"});return [{"key":x.key,"enabled":x.enabled,"version":x.version,"updated_by":x.updated_by,"updated_at":x.updated_at} for x in db.scalars(select(FeatureFlag).order_by(FeatureFlag.key)).all()]

@app.patch("/api/admin/feature-flags/{key}")
def update_feature_flag(key: str, body: dict, request: Request, x_role: str|None=Header(None), x_actor: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"});row=db.get(FeatureFlag,key)
    if not row: raise HTTPException(404,"기능 플래그를 찾을 수 없습니다.")
    before={"enabled":row.enabled,"version":row.version};row.enabled=bool(body.get("enabled"));row.version+=1;row.updated_by=x_actor or "admin";row.updated_at=datetime.now(timezone.utc);record_audit(db,action="FEATURE_FLAG_CHANGED",target_id=key,request_id=request.headers.get("X-Request-ID","generated"),before=before,after={"enabled":row.enabled,"version":row.version},actor_role="ADMIN");db.commit();return {"key":row.key,"enabled":row.enabled,"version":row.version}

@app.post("/api/label-tasks")
def create_label_task(body: dict, request: Request, x_role: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN","REVIEWER"});image_hash=str(body.get("image_hash","")).lower()
    if len(image_hash)!=64 or any(c not in "0123456789abcdef" for c in image_hash): raise HTTPException(422,"SHA-256 image_hash가 필요합니다.")
    row=LabelTask(image_hash=image_hash,assignee=body.get("assignee"));db.add(row);db.flush();record_audit(db,action="LABEL_TASK_CREATED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"image_hash":image_hash},actor_role=(x_role or "REVIEWER").upper());db.commit();return {"task_id":row.id,"status":row.status}

@app.get("/api/label-tasks")
def label_tasks(db: Session=Depends(get_db)):
    return [{"task_id":x.id,"image_hash":x.image_hash,"assignee":x.assignee,"status":x.status,"first_review":x.first_review,"second_review":x.second_review,"final_label":x.final_label} for x in db.scalars(select(LabelTask).order_by(LabelTask.updated_at.desc())).all()]

@app.post("/api/label-tasks/{task_id}/reviews")
def submit_label_review(task_id: str, body: dict, request: Request, x_role: str|None=Header(None), x_actor: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"REVIEWER","ADMIN"});row=db.get(LabelTask,task_id)
    if not row: raise HTTPException(404,"라벨 작업을 찾을 수 없습니다.")
    reviewer=x_actor or "anonymous-reviewer";review={"reviewer":reviewer,"labels":body.get("labels",{}),"comment":body.get("comment","") ,"reviewed_at":datetime.now(timezone.utc).isoformat()}
    if not row.first_review: row.first_review=review;row.status="FIRST_REVIEWED"
    elif row.first_review.get("reviewer")==reviewer: raise HTTPException(409,"두 번째 검수자는 첫 번째 검수자와 달라야 합니다.")
    elif not row.second_review: row.second_review=review;row.status="SECOND_REVIEWED" if row.first_review.get("labels")==review["labels"] else "DISAGREEMENT";row.final_label=review["labels"] if row.status=="SECOND_REVIEWED" else None
    else: raise HTTPException(409,"독립 검수 두 건이 이미 등록되었습니다.")
    row.history=list(row.history or [])+[review];row.updated_at=datetime.now(timezone.utc);record_audit(db,action="LABEL_REVIEW_SUBMITTED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"status":row.status},actor_role=(x_role or "REVIEWER").upper());db.commit();return {"task_id":row.id,"status":row.status}

@app.post("/api/label-tasks/{task_id}/adjudicate")
def adjudicate(task_id: str, body: dict, request: Request, x_role: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"});row=db.get(LabelTask,task_id)
    if not row: raise HTTPException(404,"라벨 작업을 찾을 수 없습니다.")
    row.final_label=body.get("labels",{});row.status="APPROVED";row.updated_at=datetime.now(timezone.utc);record_audit(db,action="LABEL_ADJUDICATED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"status":"APPROVED"},actor_role="ADMIN",reason=body.get("comment"));db.commit();return {"task_id":row.id,"status":row.status,"final_label":row.final_label}

@app.get("/api/label-tasks/export.csv")
def export_labels_csv(db: Session=Depends(get_db)):
    rows=db.scalars(select(LabelTask).where(LabelTask.status=="APPROVED")).all();out=__import__('io').StringIO();w=csv.writer(out);w.writerow(["anonymous_image_hash","labels_json","status"])
    for x in rows:w.writerow([x.image_hash,__import__('json').dumps(x.final_label,ensure_ascii=False),x.status])
    return Response(('\ufeff'+out.getvalue()).encode(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=labels.csv"})

@app.get("/api/lineage/{asset_hash}")
def lineage(asset_hash: str, db: Session=Depends(get_db)):
    return [{c.name:getattr(x,c.name) for c in LineageEvent.__table__.columns} for x in db.scalars(select(LineageEvent).where(LineageEvent.asset_hash==asset_hash).order_by(LineageEvent.created_at)).all()]

@app.get("/api/notifications")
def notifications(db: Session=Depends(get_db)):
    return [{"id":x.id,"event_type":x.event_type,"message":x.message,"severity":x.severity,"read":x.read,"created_at":x.created_at} for x in db.scalars(select(Notification).order_by(Notification.created_at.desc()).limit(100)).all()]

@app.post("/api/defects")
def create_defect(body: dict, request: Request, x_role: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN","REVIEWER"});identifier=f"BUG-XR-{(db.scalar(select(func.count()).select_from(Defect)) or 0)+1:03d}";required=("title","severity","reproduction_steps","expected_result","actual_result","affected_version")
    if any(not body.get(x) for x in required): raise HTTPException(422,"필수 결함 정보가 누락되었습니다.")
    row=Defect(id=identifier,**{x:body[x] for x in required},assignee=body.get("assignee"));db.add(row);record_audit(db,action="DEFECT_CREATED",target_id=identifier,request_id=request.headers.get("X-Request-ID","generated"),after={"severity":row.severity,"status":row.status},actor_role=(x_role or "REVIEWER").upper());db.commit();return {"defect_id":row.id,"status":row.status}

@app.post("/api/capas")
def create_capa(body: dict, request: Request, x_role: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"});defect=db.get(Defect,body.get("defect_id"))
    if not defect: raise HTTPException(404,"연결할 결함을 찾을 수 없습니다.")
    identifier=f"CAPA-XR-{(db.scalar(select(func.count()).select_from(Capa)) or 0)+1:03d}";row=Capa(id=identifier,defect_id=defect.id,root_cause=body.get("root_cause",""),corrective_action=body.get("corrective_action",""),preventive_action=body.get("preventive_action",""));db.add(row);defect.capa_id=identifier;record_audit(db,action="CAPA_CREATED",target_id=identifier,request_id=request.headers.get("X-Request-ID","generated"),after={"defect_id":defect.id},actor_role="ADMIN");db.commit();return {"capa_id":row.id,"defect_id":defect.id,"status":row.status}

@app.post("/api/imaging-hub/route")
def imaging_hub_route(body: dict):
    modality=str(body.get("modality","")).upper();route={"DX":"XRAY_API","CR":"XRAY_API","MR":"MRI_ADAPTER","CT":"UNSUPPORTED_QUEUE","US":"UNSUPPORTED_QUEUE"}.get(modality,"UNSUPPORTED_QUEUE")
    return {"modality":modality or "UNKNOWN","route":route,"adapter_contract":{"input_formats":["DICOM","NIFTI","PNG","JPEG"],"required_fields":["modality","study_id","series_id"],"shared_services":["deidentification","validation","job_status","audit","report_export"]},"external_call_performed":False}
