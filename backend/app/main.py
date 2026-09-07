import base64, csv, json, logging, time, uuid, zipfile
from io import BytesIO
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
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
from app.db.models import AIRisk, ActiveLearningCandidate, AgentActionProposal, AgentConversation, AgentFeedback, AgentMessage, AgentRetrievalEvent, AgentRun, AnalysisProvenance, AnnotationRecord, AuditEvent, AuditPackage, Capa, ClinicalReview, CodeMapping, ConsistencyEvidence, ConsistencyFindingRecord, ConsistencyResolution, ConsistencyRuleVersion, ConsistencyValidationRun, DatasetVersion, Defect, DefectRecord, ErrorOccurrence, ExplanationArtifact, FeatureFlag, FindingPredictionRecord, IntegrationEvent, KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentVersion, KnowledgeIndexRun, LabelTask, LatencyRecord, LineageEvent, LLMInferenceEvent, LongitudinalComparison, MisclassificationReport, ModelDeployment, ModelRegistry, ModelRelease, Notification, OperationalCapa, PipelineRun, Prediction, ProtocolDefinition, RecoveryJob, ReviewPriorityRule, RoutingRule, SecurityEvent, Study, StudyAnalysis, StudyInstance, TestEvidence, TestExecution, TestRequirement, TestScenario, UserConsent, XrayAnalysis
from app.schemas import AgentActionIn, AgentChatIn, AgentFeedbackIn, CodeMappingIn, ConsentIn, IntegratedReviewIn, MisclassificationReportIn, PredictionOut, ProtocolIn, ReviewUpdate, RoutingRuleIn, StudyTagsIn, ValidationOut
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
from app.services.medical_agent import mask_sensitive, run_agent
from app.services.responsible_ai import CONSENT_ITEMS, CONSENT_VERSION, DATASET_CARDS, GLOSSARY, MODEL_CARDS, REPORT_TYPES, RISKS, confidence_explanation, percentile
from app.services.advanced_workflows import DISCLAIMER as RESEARCH_DISCLAIMER, build_manifest, comparison_compatibility, failure_metrics
from app.services.operations import DEFAULT_THRESHOLDS, priority_decision, validate_clinical_context
from app.services.pacs import integration_status
from xray_findings import FindingInferenceEngine
from xray_findings.postprocess import near_threshold

configure_logging()
logger = logging.getLogger("xray.api")
limiter = SlidingWindowLimiter(settings.rate_limit_per_minute)
Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.app_name, version="0.1.0", description="연구·교육용 영상 분류 API이며 진단용이 아닙니다.")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"] ,allow_headers=["*"])
finding_engine=FindingInferenceEngine()
ops_metrics={"requests":0,"errors":0,"recent_errors":[]}
ops_metrics={"requests":0,"errors":0,"recent_errors":[]}
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    with next(get_db()) as db:
        defaults={"CHEST":(["PA","AP"],["LATERAL"]),"KNEE":(["AP","LATERAL"],[]),"HAND_WRIST":(["PA","OBLIQUE","LATERAL"],[]),"ANKLE":(["AP","MORTISE","LATERAL"],[]),"CERVICAL_SPINE":(["AP","LATERAL"],[])}
        for region,(required,optional) in defaults.items():
            if not db.scalar(select(ProtocolDefinition).where(ProtocolDefinition.region==region)): db.add(ProtocolDefinition(region=region,required_views=required,optional_views=optional))
        for key in ("ENABLE_DICOM_SR","ENABLE_FHIR","ENABLE_OCR","ENABLE_DETECTION","ENABLE_ENSEMBLE","ENABLE_SHADOW_MODEL","ENABLE_DRIFT_MONITORING","ENABLE_REPORT_EXPORT"):
            if not db.get(FeatureFlag,key): db.add(FeatureFlag(key=key,enabled=key in {"ENABLE_DICOM_SR","ENABLE_FHIR","ENABLE_REPORT_EXPORT"}))
        for risk_id,name,control,test,owner,residual in RISKS:
            if not db.get(AIRisk,risk_id): db.add(AIRisk(id=risk_id,name=name,control=control,verification_test=test,owner=owner,residual_risk=residual))
        if not db.scalar(select(ReviewPriorityRule).where(ReviewPriorityRule.active==True)):db.add(ReviewPriorityRule(version="1.0",thresholds=DEFAULT_THRESHOLDS,changed_by="system",change_reason="initial safe defaults"))
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
    started=time.perf_counter(); response=await call_next(request);ops_metrics["requests"]+=1
    if response.status_code>=400:
        ops_metrics["errors"]+=1;ops_metrics["recent_errors"]=(ops_metrics["recent_errors"]+[{"path":request.url.path,"status":response.status_code,"at":datetime.now(timezone.utc).isoformat()}])[-20:]
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
    started=time.perf_counter(); stage_started=time.perf_counter(); data=await file.read(); upload_ms=(time.perf_counter()-stage_started)*1000
    stage_started=time.perf_counter(); v=validate_upload(file.filename or "",file.content_type or "",data); digest=file_digest(data); decode_ms=(time.perf_counter()-stage_started)*1000
    stage_started=time.perf_counter(); lat=view="UNKNOWN"; body=None
    if v.dicom is not None: lat,view,body=metadata_orientation(v.dicom)
    deidentify_ms=(time.perf_counter()-stage_started)*1000
    stage_started=time.perf_counter(); quality=assess_image_quality(v.pixels); preprocess_ms=(time.perf_counter()-stage_started)*1000
    stage_started=time.perf_counter(); top=inference_engine.predict(v.pixels,digest); inference_ms=(time.perf_counter()-stage_started)*1000
    extended=assess_extended(v.pixels,top,v.dicom,quality)
    policy_quality=tuple(set(quality.reasons)|set(extended.quality_reasons)|set(extended.metadata_warnings)|({"OUT_OF_DISTRIBUTION"} if extended.distribution_status!="IN_DISTRIBUTION" else set()))
    required,reasons=review_decision(top,lat,view,body,policy_quality)
    p=Prediction(file_hash=digest,file_format=v.format,width=v.width,height=v.height,anatomical_region=top[0]["class"],confidence=top[0]["confidence"],top_predictions=top,laterality=lat,view_position=view,review_required=required,review_reasons=reasons,model_version=settings.model_version,dummy_mode=True,processing_time_ms=max(1,int((time.perf_counter()-started)*1000)))
    pipeline=run_multistage(v,top,digest,lat,view,body); run=PipelineRun(input_hash=digest,status=pipeline["status"],final_route=pipeline["final_route"],stages=pipeline["stages"])
    db.add(p); db.add(run); db.flush(); db.add(LineageEvent(asset_hash=digest,stage="PREDICTION",input_hash=digest,output_hash=file_digest(str(top).encode()),code_version=settings.code_version,config_version="runtime-v1",success=True)); db.add(Notification(event_type="prediction.review_required" if required else "prediction.completed",message="분석 결과가 검토 대기열에 등록되었습니다." if required else "분석이 완료되었습니다.",severity="WARNING" if required else "INFO")); record_audit(db,action="PREDICTION_CREATED",target_id=p.id,request_id=request.headers.get("X-Request-ID","generated"),after={"region":p.anatomical_region,"review_required":p.review_required,"pipeline_run_id":run.id})
    db_started=time.perf_counter(); db.commit(); db.refresh(p); database_ms=(time.perf_counter()-db_started)*1000
    total_ms=(time.perf_counter()-started)*1000
    stages={"file_upload":round(upload_ms,3),"dicom_decode":round(decode_ms,3),"deidentification":round(deidentify_ms,3),"preprocessing":round(preprocess_ms,3),"ai_inference":round(inference_ms,3),"gradcam":0.0,"database_save":round(database_ms,3)}
    db.add(LatencyRecord(prediction_id=p.id,model_version=p.model_version,device="CPU",stages_ms=stages,total_ms=round(total_ms,3),timed_out=False)); db.commit()
    result=serialize(p); result.processing_time_ms=max(1,round(total_ms)); result.preview_data_url=preview_url(v.pixels)
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

def _integrated_payload(row:XrayAnalysis,findings:list[FindingPredictionRecord]):
    return {"analysis_id":row.id,"file":{"anonymous_hash":row.anonymous_hash,"modality":row.modality,"is_dicom":row.is_dicom},"quality":row.quality,"anatomical_region":row.region_result,"screening":{"status":row.screening_status},"findings":[{"code":x.code,"display_name":x.display_name,"probability":x.probability,"threshold":x.threshold,"positive":x.positive} for x in findings],"explanation":{"available":False,"type":None,"heatmap_url":None},"uncertainty":row.uncertainty,"routing":row.routing,"model":row.model_info,"disclaimer":"연구·교육용 분석 지원 결과이며 의료진의 진단을 대체하지 않습니다."}

def _run_integrated(data:bytes,filename:str,content_type:str,db:Session):
    v=validate_upload(filename,content_type,data);digest=file_digest(data);top=inference_engine.predict(v.pixels,digest);quality=assess_image_quality(v.pixels);lat=view="UNKNOWN";body=None
    if v.dicom is not None:lat,view,body=metadata_orientation(v.dicom)
    extended=assess_extended(v.pixels,top,v.dicom,quality);finding_result=finding_engine.predict(data);finding_rows=finding_result.findings
    reasons=[]
    if extended.quality_status=="REJECT":reasons.append("QUALITY_REJECTED")
    if extended.distribution_status!="IN_DISTRIBUTION":reasons.append("OUT_OF_DISTRIBUTION")
    if top[0]["confidence"]<.75:reasons.append("LOW_REGION_CONFIDENCE")
    if near_threshold(finding_rows):reasons.append("FINDING_NEAR_THRESHOLD")
    if extended.metadata_status=="CONFLICT":reasons.append("METADATA_CONFLICT")
    positives=[x for x in finding_rows if x.positive]
    if positives:reasons.append("ABNORMALITY_SUSPECTED")
    status="QUALITY_REJECTED" if "QUALITY_REJECTED" in reasons else "OUT_OF_DISTRIBUTION" if "OUT_OF_DISTRIBUTION" in reasons else "REVIEW_REQUIRED" if any(x in reasons for x in ("LOW_REGION_CONFIDENCE","FINDING_NEAR_THRESHOLD","METADATA_CONFLICT")) else "ABNORMALITY_SUSPECTED" if positives else "NO_SIGNIFICANT_FINDING"
    review=bool(reasons);priority="HIGH" if status in ("QUALITY_REJECTED","OUT_OF_DISTRIBUTION") else "MEDIUM" if review else "LOW"
    entropy_info=uncertainty([x["confidence"] for x in top]);modality=str(getattr(v.dicom,"Modality","DX" if v.format!="DICOM" else "UNKNOWN"))
    row=XrayAnalysis(anonymous_hash=digest,modality=modality,is_dicom=v.dicom is not None,quality={"status":extended.quality_status,"score":extended.quality_score,"issues":list(extended.quality_reasons)},region_result={"code":top[0]["class"],"display_name":REGIONS[top[0]["class"]],"confidence":top[0]["confidence"],"top_predictions":top},screening_status=status,uncertainty={"entropy":entropy_info["predictive_entropy"],"ood_status":extended.distribution_status},routing={"review_required":review,"priority":priority,"reasons":reasons},model_info={"region_model_version":settings.model_version,"finding_model_version":finding_result.model_version,"finding_model_name":finding_result.model_name,"checkpoint_hash":finding_result.checkpoint_hash,"dummy_mode":True})
    db.add(row);db.flush();db.add(AnalysisProvenance(analysis_id=row.id,input_sha256=digest,raw_input_retained=False,manifest={"input_sha256":digest,"preprocessing_pipeline_version":"grayscale-normalize-v1","preprocessing_config":{"color_mode":"L","resize":"model-managed"},"region_model_version":settings.model_version,"finding_model_version":finding_result.model_version,"checkpoint_sha256":finding_result.checkpoint_hash,"dataset_version":"UNSPECIFIED","threshold_version":"finding-thresholds-v1","routing_rule_version":"integrated-routing-v1","application_version":app.version,"executed_at":datetime.now(timezone.utc).isoformat(),"environment":settings.environment,"random_seed":42}));records=[]
    for x in finding_rows:
        record=FindingPredictionRecord(analysis_id=row.id,code=x.code,display_name=x.display_name,probability=x.probability,threshold=x.threshold,positive=x.positive);db.add(record);records.append(record)
    db.add(ExplanationArtifact(analysis_id=row.id,artifact_type="GRAD_CAM",available=False));db.commit();return _integrated_payload(row,records)

@app.post("/api/v1/xray/analyze")
async def integrated_analyze(file:UploadFile=File(...),db:Session=Depends(get_db)):
    data=await file.read();return _run_integrated(data,file.filename or "",file.content_type or "",db)

@app.post("/api/v1/xray/analyze-batch")
async def integrated_batch(files:list[UploadFile]=File(...),db:Session=Depends(get_db)):
    if len(files)>20:raise HTTPException(413,"배치는 최대 20개 파일입니다.")
    blobs=[];total=0
    for file in files:
        data=await file.read();total+=len(data)
        if total>50*1024*1024:raise HTTPException(413,"배치 전체 용량은 50MB를 초과할 수 없습니다.")
        if (file.filename or "").lower().endswith(".zip"):
            inspect_zip(data,max_files=20,max_uncompressed=50*1024*1024)
            with zipfile.ZipFile(BytesIO(data)) as archive:
                for info in archive.infolist():
                    if not info.is_dir():blobs.append((info.filename,archive.read(info),"application/dicom" if info.filename.lower().endswith(".dcm") else "image/png" if info.filename.lower().endswith(".png") else "image/jpeg"))
        else:blobs.append((file.filename or "",data,file.content_type or ""))
    if len(blobs)>20:raise HTTPException(413,"압축 해제 후 파일 수는 최대 20개입니다.")
    results=[]
    for name,data,mime in blobs:
        try:results.append({"file":name,"status":"SUCCESS","result":_run_integrated(data,name,mime,db)})
        except Exception as exc:db.rollback();results.append({"file":name,"status":"FAILED","error":str(exc)})
    return {"count":len(results),"results":results}

@app.get("/api/v1/xray/analyses/{analysis_id}")
def integrated_get(analysis_id:str,db:Session=Depends(get_db)):
    row=db.get(XrayAnalysis,analysis_id)
    if not row:raise HTTPException(404,"통합 분석 결과를 찾을 수 없습니다.")
    findings=db.scalars(select(FindingPredictionRecord).where(FindingPredictionRecord.analysis_id==analysis_id)).all();return _integrated_payload(row,findings)

@app.get("/api/v1/xray/analyses/{analysis_id}/heatmap")
def integrated_heatmap(analysis_id:str,db:Session=Depends(get_db)):
    if not db.get(XrayAnalysis,analysis_id):raise HTTPException(404,"통합 분석 결과를 찾을 수 없습니다.")
    raise HTTPException(404,"DUMMY 모델은 실제 Grad-CAM을 제공하지 않습니다.")

@app.get("/api/v1/xray/analyses/{analysis_id}/report")
def integrated_report(analysis_id:str,db:Session=Depends(get_db)):
    row=db.get(XrayAnalysis,analysis_id)
    if not row:raise HTTPException(404,"통합 분석 결과를 찾을 수 없습니다.")
    data=_simple_pdf(["Integrated X-Ray AI Support Report",f"Anonymous ID: {row.id}",f"Region: {row.region_result['code']}",f"Screening: {row.screening_status}",f"Model: {row.model_info['finding_model_version']} (DUMMY)","Research and education only. Not a medical diagnosis."])
    return Response(data,media_type="application/pdf",headers={"Content-Disposition":f"attachment; filename={row.id}.pdf"})

@app.get("/api/v1/xray/worklist")
def integrated_worklist(reason:str|None=None,status:str|None=None,db:Session=Depends(get_db)):
    rows=db.scalars(select(XrayAnalysis).order_by(XrayAnalysis.created_at.desc())).all();out=[]
    for row in rows:
        if not row.routing.get("review_required") or (reason and reason not in row.routing.get("reasons",[])) or (status and row.screening_status!=status):continue
        out.append({"analysis_id":row.id,"screening_status":row.screening_status,"priority":row.routing["priority"],"reasons":row.routing["reasons"],"created_at":row.created_at})
    return sorted(out,key=lambda x:({"HIGH":0,"MEDIUM":1,"LOW":2}[x["priority"]],x["created_at"]),reverse=False)

@app.patch("/api/v1/xray/analyses/{analysis_id}/review")
def integrated_review(analysis_id:str,body:IntegratedReviewIn,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"REVIEWER","ADMIN"});row=db.get(XrayAnalysis,analysis_id)
    if not row:raise HTTPException(404,"통합 분석 결과를 찾을 수 없습니다.")
    before={"region":row.region_result["code"],"findings":[x.code for x in db.scalars(select(FindingPredictionRecord).where(FindingPredictionRecord.analysis_id==analysis_id,FindingPredictionRecord.positive==True)).all()]};after={"region":body.final_region,"findings":body.final_findings}
    event=record_audit(db,action="XRAY_ANALYSIS_REVIEWED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),before=before,after=after,reason=body.comment,actor_role=role);db.flush();db.add(ClinicalReview(analysis_id=row.id,reviewer_role=role,final_region=body.final_region,final_findings=body.final_findings,comment=body.comment,before_value=before,after_value=after,audit_event_id=getattr(event,"id",None)));db.add(ActiveLearningCandidate(analysis_id=row.id,anonymous_hash=row.anonymous_hash,original_labels=before,corrected_labels=after,model_version=row.model_info.get("finding_model_version","UNKNOWN"),auto_training_enabled=False));row.reviewed=True;row.routing={**row.routing,"review_required":False,"review_status":"COMPLETED"};db.commit();return {"analysis_id":row.id,"reviewed":True,"before":before,"after":after,"active_learning_candidate":True,"automatic_retraining":False}

@app.post("/api/v1/xray/longitudinal-comparisons")
def create_longitudinal_comparison(body:dict,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    require_role(x_role,{"REVIEWER","ADMIN"});prior=db.get(XrayAnalysis,body.get("prior_analysis_id"));current=db.get(XrayAnalysis,body.get("current_analysis_id"))
    if not prior or not current:raise HTTPException(404,"비교할 분석 결과를 찾을 수 없습니다.")
    compatibility=comparison_compatibility(body.get("prior_context",{}),body.get("current_context",{}))
    def positives(row):return {x.code for x in db.scalars(select(FindingPredictionRecord).where(FindingPredictionRecord.analysis_id==row.id,FindingPredictionRecord.positive==True)).all()}
    old,new=positives(prior),positives(current);changes={"region_changed":prior.region_result["code"]!=current.region_result["code"],"new_findings":sorted(new-old),"resolved_findings":sorted(old-new),"interpretation":"변화 탐지 결과는 의료진 확인 전 확정되지 않습니다."}
    row=LongitudinalComparison(prior_analysis_id=prior.id,current_analysis_id=current.id,compatibility=compatibility,changes=changes);db.add(row);db.commit();return {"comparison_id":row.id,"compatibility":compatibility,"changes":changes,"review_required":True,"disclaimer":RESEARCH_DISCLAIMER}

@app.get("/api/v1/xray/longitudinal-comparisons/{comparison_id}")
def get_longitudinal_comparison(comparison_id:str,db:Session=Depends(get_db)):
    row=db.get(LongitudinalComparison,comparison_id)
    if not row:raise HTTPException(404,"비교 결과를 찾을 수 없습니다.")
    return {"comparison_id":row.id,"prior_analysis_id":row.prior_analysis_id,"current_analysis_id":row.current_analysis_id,"compatibility":row.compatibility,"changes":row.changes,"review_status":row.review_status,"disclaimer":RESEARCH_DISCLAIMER}

@app.get("/api/v1/active-learning/candidates")
def active_candidates(x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    require_role(x_role,{"REVIEWER","ADMIN"});rows=db.scalars(select(ActiveLearningCandidate).order_by(ActiveLearningCandidate.created_at.desc())).all();return [{"candidate_id":x.id,"analysis_id":x.analysis_id,"anonymous_hash":x.anonymous_hash,"original_labels":x.original_labels,"corrected_labels":x.corrected_labels,"model_version":x.model_version,"approved_for_export":x.approved_for_export,"automatic_retraining":x.auto_training_enabled} for x in rows]

@app.post("/api/v1/datasets")
def create_dataset(body:dict,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"})
    try:manifest,duplicates=build_manifest(body.get("items",[]))
    except ValueError as exc:raise HTTPException(422,str(exc))
    row=DatasetVersion(name=str(body.get("name","xray-dataset"))[:100],version=str(body.get("version","v1"))[:32],status="DRAFT",manifest=manifest,duplicate_count=duplicates);db.add(row);db.commit();return {"dataset_id":row.id,"name":row.name,"version":row.version,"status":row.status,"deidentification":"HASH_ONLY_NO_RAW_IDENTIFIERS","duplicates_removed":duplicates,"patient_level_split":True,"items":manifest,"performance":"NOT_MEASURED"}

@app.post("/api/v1/datasets/{dataset_id}/approve")
def approve_dataset(dataset_id:str,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"});row=db.get(DatasetVersion,dataset_id)
    if not row:raise HTTPException(404,"데이터셋 버전을 찾을 수 없습니다.")
    if any(x.get("label_status")!="APPROVED" for x in row.manifest):raise HTTPException(409,"모든 다중 소견 라벨의 승인이 필요합니다.")
    row.status="APPROVED";db.commit();return {"dataset_id":row.id,"status":row.status}

@app.get("/api/v1/datasets/{dataset_id}/manifest.csv")
def dataset_manifest(dataset_id:str,db:Session=Depends(get_db)):
    row=db.get(DatasetVersion,dataset_id)
    if not row:raise HTTPException(404,"데이터셋 버전을 찾을 수 없습니다.")
    out=__import__('io').StringIO();writer=csv.writer(out);writer.writerow(["anonymous_hash","patient_hash","split","region","findings","label_status","dataset_version"])
    for x in row.manifest:writer.writerow([x["anonymous_hash"],x["patient_hash"],x["split"],x["region"],"|".join(x["findings"]),x["label_status"],row.version])
    return Response(('\ufeff'+out.getvalue()).encode(),media_type="text/csv",headers={"Content-Disposition":f"attachment; filename={row.name}-{row.version}.csv"})

@app.post("/api/v1/failure-analysis")
def failure_analysis(body:dict,x_role:str|None=Header(default=None,alias="X-Role")):
    require_role(x_role,{"REVIEWER","ADMIN"});return {**failure_metrics(body.get("validated_cases",[])),"quality_breakdown":"NOT_MEASURED" if not body.get("validated_cases") else "REQUIRES_QUALITY_LABELS","institution_equipment_breakdown":"INSUFFICIENT_SAMPLE","disclaimer":RESEARCH_DISCLAIMER}

@app.post("/api/v1/model-monitoring/deployments")
def register_deployment(body:dict,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"});sha=str(body.get("checkpoint_sha256","")).lower()
    if len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha):raise HTTPException(422,"체크포인트 SHA-256이 필요합니다.")
    row=ModelDeployment(model_version=body.get("model_version","UNKNOWN"),checkpoint_sha256=sha,dataset_version=body.get("dataset_version","UNSPECIFIED"),deployment_status=body.get("deployment_status","DEMO_ONLY"),performance_status="NOT_MEASURED",drift_status="INSUFFICIENT_DATA");db.add(row);db.commit();return {"deployment_id":row.id,"model_version":row.model_version,"checkpoint_sha256":row.checkpoint_sha256,"dataset_version":row.dataset_version,"deployment_status":row.deployment_status,"performance_status":row.performance_status,"drift_status":row.drift_status}

@app.get("/api/v1/model-monitoring")
def model_monitoring(db:Session=Depends(get_db)):
    rows=db.scalars(select(ModelDeployment).order_by(ModelDeployment.created_at.desc())).all();return {"deployments":[{"deployment_id":x.id,"model_version":x.model_version,"checkpoint_sha256":x.checkpoint_sha256,"dataset_version":x.dataset_version,"deployment_status":x.deployment_status,"performance_status":x.performance_status,"drift_status":x.drift_status} for x in rows],"rule":"실제 검증 정답과 기준 기간 데이터가 없으면 성능 저하·드리프트 수치를 생성하지 않습니다."}

@app.get("/api/v1/regulatory-documents")
def regulatory_documents():
    names=[("SRS","요구사항 명세서"),("RISK","위험관리표"),("VVP","검증 계획서"),("VTR","시험 결과 보고서"),("MCIA","모델 변경 영향평가"),("TRACE","추적성 매트릭스")]
    return [{"document_id":code,"title":title,"status":"AUTO_GENERATED_DRAFT","review_required":True,"download_url":f"/api/v1/regulatory-documents/{code}.md"} for code,title in names]

@app.get("/api/v1/regulatory-documents/{document_id}.md")
def regulatory_document(document_id:str):
    allowed={"SRS":"요구사항 명세서","RISK":"위험관리표","VVP":"검증 계획서","VTR":"시험 결과 보고서","MCIA":"모델 변경 영향평가","TRACE":"추적성 매트릭스"}
    if document_id not in allowed:raise HTTPException(404,"문서를 찾을 수 없습니다.")
    content=f"# {allowed[document_id]}\n\n상태: 자동 생성 초안 / 승인 전 사용 금지\n\n- 시스템: X-ray 연구·교육용 분석 지원\n- 성능: NOT_MEASURED (실제 검증 데이터 없음)\n- 사람 검토: 필수\n- 생성 시각: {datetime.now(timezone.utc).isoformat()}\n\n{RESEARCH_DISCLAIMER}\n"
    return Response(content,media_type="text/markdown",headers={"Content-Disposition":f"attachment; filename={document_id}.md"})

@app.get("/api/v1/integrations/status")
def integrations_status():
    from app.services.pacs import integration_status
    return {**integration_status(),"database":"UP","model":"DUMMY_READY" if settings.dummy_mode else "CONFIGURED","queue":"LOCAL_ONLY"}

@app.get("/api/v1/analyses/{analysis_id}/provenance")
def analysis_provenance(analysis_id:str,db:Session=Depends(get_db)):
    row=db.get(AnalysisProvenance,analysis_id)
    if not row:raise HTTPException(404,"분석 provenance를 찾을 수 없습니다.")
    return {"analysis_id":analysis_id,**row.manifest,"raw_input_retained":row.raw_input_retained}

@app.post("/api/v1/analyses/{analysis_id}/reproduce")
def reproduce_analysis(analysis_id:str,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"ML_ENGINEER","QA_RA","ADMIN"});row=db.get(AnalysisProvenance,analysis_id)
    if not row:raise HTTPException(404,"분석 provenance를 찾을 수 없습니다.")
    if not row.raw_input_retained:
        record_audit(db,action="ANALYSIS_REPRODUCE_BLOCKED",target_id=analysis_id,request_id=request.headers.get("X-Request-ID","generated"),after={"reason":"RAW_INPUT_NOT_RETAINED"},actor_role=role);db.commit();raise HTTPException(409,"RAW_INPUT_NOT_RETAINED: 개인정보 보호 정책에 따라 원본 영상이 보존되지 않아 재현할 수 없습니다.")
    return {"status":"QUEUED"}

@app.get("/api/v1/analyses/{analysis_id}/compare/{other_id}")
def compare_analyses(analysis_id:str,other_id:str,db:Session=Depends(get_db)):
    first,second=db.get(XrayAnalysis,analysis_id),db.get(XrayAnalysis,other_id)
    if not first or not second:raise HTTPException(404,"비교할 분석을 찾을 수 없습니다.")
    p1,p2=db.get(AnalysisProvenance,analysis_id),db.get(AnalysisProvenance,other_id);f=lambda i:{x.code:round(x.probability,6) for x in db.scalars(select(FindingPredictionRecord).where(FindingPredictionRecord.analysis_id==i)).all()}
    stable={"preprocessing_pipeline_version","preprocessing_settings","anatomical_region_model_version","finding_model_version","model_checkpoint_sha256","dataset_version","finding_threshold_version","routing_rule_version","application_version","execution_environment","random_seed"}
    same_settings=bool(p1 and p2 and all(p1.manifest.get(k)==p2.manifest.get(k) for k in stable));a,b=f(analysis_id),f(other_id);return {"same_input":bool(p1 and p2 and p1.input_sha256==p2.input_sha256),"same_settings":same_settings,"region":{"first":first.region_result["code"],"second":second.region_result["code"],"changed":first.region_result["code"]!=second.region_result["code"]},"finding_probability_deltas":{k:round(b.get(k,0)-a.get(k,0),6) for k in sorted(set(a)|set(b))},"review_required":True,"disclaimer":RESEARCH_DISCLAIMER}

@app.post("/api/v1/test-requirements")
def create_test_requirement(body:dict,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    require_role(x_role,{"QA_RA","ADMIN"});row=TestRequirement(requirement_id=body.get("requirement_id"),risk_ids=body.get("risk_ids",[]),title=body.get("title",""));db.add(row);db.commit();return {"id":row.id,"requirement_id":row.requirement_id}

@app.post("/api/v1/test-scenarios")
def create_test_scenario(body:dict,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    require_role(x_role,{"QA_RA","ADMIN"});types={"NORMAL","BOUNDARY","NEGATIVE","SECURITY","PERFORMANCE","RECOVERY","USABILITY"}
    if body.get("scenario_type") not in types:raise HTTPException(422,"지원하지 않는 시험 유형입니다.")
    row=TestScenario(test_id=body.get("test_id"),requirement_id=body.get("requirement_id"),risk_ids=body.get("risk_ids",[]),scenario_type=body["scenario_type"],preconditions=body.get("preconditions",""),input_data=body.get("input_data",{}),steps=body.get("steps",[]),expected_result=body.get("expected_result",""));db.add(row);db.commit();return {"scenario_id":row.id,"test_id":row.test_id}

@app.post("/api/v1/test-scenarios/{scenario_id}/executions")
def execute_test_scenario(scenario_id:str,body:dict,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"QA_RA","ADMIN"});scenario=db.get(TestScenario,scenario_id);status=body.get("status")
    if not scenario:raise HTTPException(404,"시험 시나리오를 찾을 수 없습니다.")
    if status not in {"PASS","FAIL","BLOCKED"}:raise HTTPException(422,"시험 결과 상태가 올바르지 않습니다.")
    row=TestExecution(scenario_id=scenario.id,actual_result=body.get("actual_result",""),status=status,tester=body.get("tester","UNKNOWN"),retest_of=body.get("retest_of"));db.add(row);db.flush()
    for item in body.get("evidence",[]):db.add(TestEvidence(execution_id=row.id,filename=item.get("filename","evidence"),sha256=item.get("sha256",""),storage_status="METADATA_ONLY"))
    if status=="FAIL":db.add(DefectRecord(execution_id=row.id,summary=body.get("defect_summary","시험 실패")))
    record_audit(db,action="TEST_EXECUTED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"test_id":scenario.test_id,"status":status},actor_role=role);db.commit();return {"execution_id":row.id,"status":row.status,"defect_created":status=="FAIL"}

@app.get("/api/v1/test-scenarios")
def list_test_scenarios(db:Session=Depends(get_db)):
    rows=db.scalars(select(TestScenario)).all();return [{"scenario_id":x.id,"test_id":x.test_id,"requirement_id":x.requirement_id,"risk_ids":x.risk_ids,"scenario_type":x.scenario_type,"preconditions":x.preconditions,"input_data":x.input_data,"steps":x.steps,"expected_result":x.expected_result} for x in rows]

@app.get("/api/v1/synthetic-safety-cases")
def list_safety_cases():
    from app.services.verification import SAFETY_CASES
    return [{"case":k,"expected_quality_status":v[0],"expected_review_required":v[1],"expected_error_code":v[2],"synthetic":True} for k,v in SAFETY_CASES.items()]

@app.post("/api/v1/synthetic-safety-cases/{case_name}")
def generate_safety_case(case_name:str):
    from app.services.verification import safety_case
    try:item=safety_case(case_name)
    except ValueError as exc:raise HTTPException(404,str(exc))
    headers={"X-Synthetic-Test-Case":item["case"],"X-Expected-Quality":item["expected_quality_status"],"X-Expected-Review":str(item["expected_review_required"]).lower(),"X-Expected-Error":item["expected_error_code"] or "NONE"};return Response(item["dicom"],media_type="application/dicom",headers=headers)

@app.post("/api/v1/annotations")
def create_annotation(body:dict,x_role:str|None=Header(default=None,alias="X-Role"),x_actor:str|None=Header(default=None,alias="X-Actor"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"LABELER","RADIOLOGIST"});image_hash=str(body.get("anonymous_image_hash","")).lower()
    if len(image_hash)!=64:raise HTTPException(422,"익명 영상 SHA-256이 필요합니다.")
    review={"reviewer":x_actor or "anonymous","role":role,"region":body.get("region"),"findings":body.get("findings",[]),"at":datetime.now(timezone.utc).isoformat()};row=AnnotationRecord(anonymous_image_hash=image_hash,first_review=review,history=[{"action":"FIRST_REVIEW","after":review}]);db.add(row);db.commit();return {"annotation_id":row.id,"status":row.status,"training_eligible":False}

@app.post("/api/v1/annotations/{annotation_id}/second-review")
def second_annotation(annotation_id:str,body:dict,x_role:str|None=Header(default=None,alias="X-Role"),x_actor:str|None=Header(default=None,alias="X-Actor"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"RADIOLOGIST"});row=db.get(AnnotationRecord,annotation_id)
    if not row:raise HTTPException(404,"라벨 작업을 찾을 수 없습니다.")
    reviewer=x_actor or "anonymous-radiologist"
    if reviewer==row.first_review.get("reviewer"):raise HTTPException(409,"두 번째 판독자는 첫 번째 판독자와 달라야 합니다.")
    review={"reviewer":reviewer,"role":role,"region":body.get("region"),"findings":body.get("findings",[]),"at":datetime.now(timezone.utc).isoformat()};row.second_review=review;agreed=review["region"]==row.first_review.get("region") and sorted(review["findings"])==sorted(row.first_review.get("findings",[]));row.status="AGREED" if agreed else "DISAGREEMENT";row.history=list(row.history)+[{"action":"SECOND_REVIEW","before":row.first_review,"after":review,"agreed":agreed}];db.commit();return {"annotation_id":row.id,"status":row.status,"agreement":agreed,"training_eligible":False}

@app.post("/api/v1/annotations/{annotation_id}/adjudicate")
def adjudicate_annotation(annotation_id:str,body:dict,x_role:str|None=Header(default=None,alias="X-Role"),x_actor:str|None=Header(default=None,alias="X-Actor"),db:Session=Depends(get_db)):
    require_role(x_role,{"ADJUDICATOR"});row=db.get(AnnotationRecord,annotation_id)
    if not row or not row.second_review:raise HTTPException(409,"독립 2차 판독 완료 후 합의 판독할 수 있습니다.")
    result={"reviewer":x_actor or "adjudicator","region":body.get("region"),"findings":body.get("findings",[]),"reason":body.get("reason",""),"at":datetime.now(timezone.utc).isoformat()};row.adjudication=result;row.status="ADJUDICATED";row.history=list(row.history)+[{"action":"ADJUDICATED","after":result}];db.commit();return {"annotation_id":row.id,"status":row.status,"training_eligible":False}

@app.post("/api/v1/annotations/{annotation_id}/approve")
def approve_annotation(annotation_id:str,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    require_role(x_role,{"ADJUDICATOR"});row=db.get(AnnotationRecord,annotation_id)
    if not row or row.status not in {"AGREED","ADJUDICATED"}:raise HTTPException(409,"합의 또는 합의 판독 완료 후 승인할 수 있습니다.")
    row.final_label=row.adjudication or row.second_review;row.status="APPROVED";row.history=list(row.history)+[{"action":"APPROVED","after":row.final_label}];db.commit();return {"annotation_id":row.id,"status":row.status,"training_eligible":True}

@app.get("/api/v1/annotations/agreement")
def annotation_agreement(db:Session=Depends(get_db)):
    rows=db.scalars(select(AnnotationRecord).where(AnnotationRecord.second_review.is_not(None))).all();total=len(rows);region=sum(x.first_review.get("region")==x.second_review.get("region") for x in rows);finding=sum(sorted(x.first_review.get("findings",[]))==sorted(x.second_review.get("findings",[])) for x in rows);return {"sample_size":total,"region_agreement":region/total if total else None,"finding_agreement":finding/total if total else None,"status":"MEASURED" if total else "INSUFFICIENT_DATA"}

@app.post("/api/v1/fairness/evaluate")
def evaluate_fairness(body:dict,x_role:str|None=Header(default=None,alias="X-Role")):
    require_role(x_role,{"ML_ENGINEER","QA_RA","ADMIN"});from app.services.verification import fairness
    try:return fairness(body.get("validated_cases",[]),body.get("group_by","age_group"),int(body.get("min_samples",20)))
    except ValueError as exc:raise HTTPException(422,str(exc))

@app.post("/api/v1/recovery/jobs")
def create_recovery_job(body:dict,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"TECHNICIAN","RADIOLOGIST","ADMIN"});key=request.headers.get("Idempotency-Key") or body.get("idempotency_key")
    if not key:raise HTTPException(422,"Idempotency-Key가 필요합니다.")
    existing=db.scalar(select(RecoveryJob).where(RecoveryJob.idempotency_key==key))
    if existing:return {"job_id":existing.id,"status":existing.status,"duplicate":True}
    failure=body.get("simulate_failure");status="RETRY_PENDING" if failure in {"MODEL_TIMEOUT","MODEL_SERVER_DOWN","WORKER_INTERRUPTED"} else "QUARANTINED" if failure in {"DATABASE_FAILURE","PARTIAL_BATCH"} else "SUCCEEDED";row=RecoveryJob(idempotency_key=key,analysis_id=body.get("analysis_id"),status=status,attempts=1,max_attempts=min(5,int(body.get("max_attempts",3))),next_retry_seconds=2 if status=="RETRY_PENDING" else 0,failure_reason=failure,model_version=body.get("model_version",settings.model_version));db.add(row);db.flush();record_audit(db,action="RECOVERY_JOB_CREATED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"status":status,"failure":failure},actor_role=role);db.commit();return {"job_id":row.id,"status":row.status,"attempts":row.attempts,"next_retry_seconds":row.next_retry_seconds,"duplicate":False,"routed_to_medical_review":failure=="MODEL_SERVER_DOWN"}

@app.post("/api/v1/recovery/jobs/{job_id}/retry")
def retry_recovery_job(job_id:str,body:dict,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"ADMIN"});row=db.get(RecoveryJob,job_id)
    if not row:raise HTTPException(404,"복구 작업을 찾을 수 없습니다.")
    row.attempts+=1
    if row.attempts>row.max_attempts:row.status="FAILED"
    elif body.get("model_rollback_completed"):row.status="SUCCEEDED";row.failure_reason=None
    else:row.status="RETRY_PENDING";row.next_retry_seconds=min(60,2**row.attempts)
    record_audit(db,action="RECOVERY_JOB_RETRIED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"status":row.status,"attempts":row.attempts},actor_role=role);db.commit();return {"job_id":row.id,"status":row.status,"attempts":row.attempts,"next_retry_seconds":row.next_retry_seconds}

@app.get("/api/v1/recovery/jobs")
def recovery_jobs(db:Session=Depends(get_db)):
    rows=db.scalars(select(RecoveryJob).order_by(RecoveryJob.created_at.desc())).all();return [{"job_id":x.id,"status":x.status,"attempts":x.attempts,"max_attempts":x.max_attempts,"failure_reason":x.failure_reason,"next_retry_seconds":x.next_retry_seconds} for x in rows]

@app.post("/api/v1/audit-packages")
def create_audit_package(body:dict,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"QA_RA","ADMIN"});from app.services.verification import build_audit_package,encode
    payload,manifest=build_audit_package(role,body.get("versions",{}));digest=file_digest(payload);row=AuditPackage(created_by_role=role,manifest=manifest,payload_base64=encode(payload),package_sha256=digest);db.add(row);db.flush();record_audit(db,action="AUDIT_PACKAGE_CREATED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"sha256":digest,"files":len(manifest["files"])+1},actor_role=role);db.commit();return {"package_id":row.id,"status":row.status,"package_sha256":digest,"manifest":manifest}

@app.get("/api/v1/audit-packages/{package_id}")
def get_audit_package(package_id:str,db:Session=Depends(get_db)):
    from app.services.verification import decode
    row=db.get(AuditPackage,package_id)
    if not row:raise HTTPException(404,"감사 패키지를 찾을 수 없습니다.")
    valid=file_digest(decode(row.payload_base64))==row.package_sha256;return {"package_id":row.id,"status":row.status if valid else "INTEGRITY_FAILED","integrity_valid":valid,"package_sha256":row.package_sha256,"manifest":row.manifest}

@app.get("/api/v1/audit-packages/{package_id}/download")
def download_audit_package(package_id:str,db:Session=Depends(get_db)):
    from app.services.verification import decode
    row=db.get(AuditPackage,package_id)
    if not row:raise HTTPException(404,"감사 패키지를 찾을 수 없습니다.")
    payload=decode(row.payload_base64)
    if file_digest(payload)!=row.package_sha256:raise HTTPException(409,"INTEGRITY_FAILED: 생성 후 패키지 내용이 변경되었습니다.")
    return Response(payload,media_type="application/zip",headers={"Content-Disposition":f"attachment; filename=audit-package-{row.id}.zip"})

@app.get("/api/v1/security/status")
def security_status():return {"upload_limits":{"max_mb":settings.max_upload_mb,"max_batch_files":20},"mime_signature_cross_check":True,"zip_path_traversal_blocked":True,"nested_zip_blocked":True,"malware_scanner":"NOT_CONFIGURED","malware_scan_completed":False,"secret_log_masking":True,"admin_reauthentication":"INTERFACE_REQUIRED_NOT_CONFIGURED"}

@app.post("/api/v1/studies/import")
async def import_study(request:Request,files:list[UploadFile]=File(...),clinical_context_json:str=Form("{}"),x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"TECHNICIAN","ADMIN"})
    from app.services.operations import validate_clinical_context
    try:context=validate_clinical_context(json.loads(clinical_context_json or "{}"))
    except (ValueError,json.JSONDecodeError) as exc:raise HTTPException(422,str(exc))
    if not files:raise HTTPException(422,"한 개 이상의 DICOM이 필요합니다.")
    items=[];seen=set();study_hash=None
    for upload in files:
        data=await upload.read();meta=dicom_group_metadata(data)
        if study_hash and meta["study_uid_hash"]!=study_hash:raise HTTPException(422,"서로 다른 StudyInstanceUID는 한 요청에서 가져올 수 없습니다.")
        study_hash=meta["study_uid_hash"]
        if meta["sop_uid_hash"] in seen or db.scalar(select(StudyInstance).where(StudyInstance.sop_uid_hash==meta["sop_uid_hash"])):raise HTTPException(409,"중복 SOPInstanceUID가 탐지되어 등록을 차단했습니다.")
        seen.add(meta["sop_uid_hash"]);result=_run_integrated(data,upload.filename or "image.dcm",upload.content_type or "application/dicom",db);items.append((meta,result))
    regions=[x[1]["anatomical_region"]["code"] for x in items];region=max(set(regions),key=regions.count);views=[x[0]["view_position"] for x in items];expected=["LATERAL",("PA_OR_AP" if region=="CHEST" else "AP")];missing=[]
    if "LATERAL" not in views:missing.append("LATERAL")
    if region=="CHEST" and not ({"PA","AP"}&set(views)):missing.append("PA_OR_AP")
    elif region!="CHEST" and "AP" not in views:missing.append("AP")
    protocol={"status":"MISSING_VIEW" if missing else "COMPLETE","required":expected,"missing":missing,"observed":sorted(set(views))}
    study=Study(study_uid_hash=study_hash or file_digest(uuid.uuid4().bytes),anonymous_accession=items[0][0]["anonymous_accession"],study_date=items[0][0]["study_date"],region=region,protocol_status=protocol["status"],views=views,tags=[{"clinical_context":context,"source":"ALLOWLISTED_INPUT"}]);db.add(study);db.flush()
    for meta,result in items:db.add(StudyInstance(study_id=study.id,series_uid_hash=meta["series_uid_hash"],sop_uid_hash=meta["sop_uid_hash"],series_number=meta["series_number"],instance_number=meta["instance_number"],view_position=meta["view_position"],laterality=meta["laterality"],prediction_id=result["analysis_id"]))
    record_audit(db,action="STUDY_IMPORTED",target_id=study.id,request_id=request.headers.get("X-Request-ID","generated"),after={"instances":len(items),"protocol":protocol},actor_role=role);db.commit();return {"study_id":study.id,"study_uid_hash":study.study_uid_hash,"instance_count":len(items),"views":views,"protocol":protocol,"clinical_context":context,"external_transmission":False}

@app.post("/api/v1/studies/{study_id}/analyze")
def analyze_study(study_id:str,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"TECHNICIAN","RADIOLOGIST","ADMIN"});study=db.get(Study,study_id)
    if not study:raise HTTPException(404,"Study를 찾을 수 없습니다.")
    instances=db.scalars(select(StudyInstance).where(StudyInstance.study_id==study.id)).all();results=[]
    for item in instances:
        analysis=db.get(XrayAnalysis,item.prediction_id) if item.prediction_id else None
        if not analysis:continue
        findings=db.scalars(select(FindingPredictionRecord).where(FindingPredictionRecord.analysis_id==analysis.id)).all();results.append({"instance_id":item.id,"view_position":item.view_position,"region":analysis.region_result["code"],"quality_status":analysis.quality["status"],"ood_status":analysis.uncertainty.get("ood_status","UNKNOWN"),"max_finding_probability":max([x.probability for x in findings] or [0]),"screening_status":analysis.screening_status})
    rule=db.scalar(select(ReviewPriorityRule).where(ReviewPriorityRule.active==True).order_by(ReviewPriorityRule.created_at.desc()))
    if not rule:rule=ReviewPriorityRule(version="1.0",thresholds={"high_priority_finding_probability":.8,"capa_repeat_count":3},changed_by="system");db.add(rule);db.flush()
    from app.services.operations import priority_decision
    decision=priority_decision(results,study.protocol_status,rule.thresholds);regions={x["region"] for x in results};aggregate={"region":next(iter(regions)) if len(regions)==1 else "CONFLICT","instance_count":len(results),"conflict":len(regions)>1,"emergency_diagnosis":False}
    context=(study.tags[0].get("clinical_context",{}) if study.tags else {});combined={"used":any(v not in ("UNKNOWN",[],None) for v in context.values()),"effect":"우선순위나 AI 점수를 자동 변경하지 않고 의료진 참고정보로만 표시합니다."}
    row=StudyAnalysis(study_id=study.id,instance_results=results,aggregate_result=aggregate,clinical_context=context,clinical_context_effect=combined,status=decision["status"],priority_reasons=decision["reasons"],priority_rule_version=rule.version);db.add(row);record_audit(db,action="STUDY_ANALYZED",target_id=study.id,request_id=request.headers.get("X-Request-ID","generated"),after={"status":row.status,"reasons":row.priority_reasons,"rule_version":rule.version},actor_role=role);db.commit();return {"analysis_id":row.id,"study_id":study.id,"instance_results":results,"study_result":aggregate,"priority":{"status":row.status,"reasons":row.priority_reasons,"rule_version":rule.version},"image_only_result":aggregate,"clinical_combined_result":{"result":aggregate,"context":context,"influence":combined},"disclaimer":"높은 우선순위는 응급 진단 확정이 아닌 의료진 우선 검토 요청입니다."}

@app.get("/api/v1/studies/{study_id}")
def get_study_v1(study_id:str,db:Session=Depends(get_db)):
    study=db.get(Study,study_id)
    if not study:raise HTTPException(404,"Study를 찾을 수 없습니다.")
    instances=db.scalars(select(StudyInstance).where(StudyInstance.study_id==study.id)).all();latest=db.scalar(select(StudyAnalysis).where(StudyAnalysis.study_id==study.id).order_by(StudyAnalysis.created_at.desc()))
    return {"study_id":study.id,"study_uid_hash":study.study_uid_hash,"region":study.region,"views":study.views,"protocol_status":study.protocol_status,"instances":[{"instance_id":x.id,"series_uid_hash":x.series_uid_hash,"sop_uid_hash":x.sop_uid_hash,"view_position":x.view_position,"analysis_id":x.prediction_id} for x in instances],"latest_analysis":None if not latest else {"analysis_id":latest.id,"status":latest.status,"reasons":latest.priority_reasons,"rule_version":latest.priority_rule_version}}

@app.get("/api/v1/worklist")
def study_worklist(status:str|None=None,db:Session=Depends(get_db)):
    rows=db.scalars(select(StudyAnalysis).order_by(StudyAnalysis.created_at.desc())).all();return [{"worklist_id":x.id,"study_id":x.study_id,"status":x.status,"reasons":x.priority_reasons,"rule_version":x.priority_rule_version,"created_at":x.created_at} for x in rows if not status or x.status==status]

@app.patch("/api/v1/worklist/{worklist_id}/priority")
def change_worklist_priority(worklist_id:str,body:dict,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"RADIOLOGIST","ADMIN"});row=db.get(StudyAnalysis,worklist_id);allowed={"ROUTINE","REVIEW_REQUIRED","HIGH_PRIORITY_REVIEW","QUALITY_REJECTED"}
    if not row:raise HTTPException(404,"워크리스트 항목을 찾을 수 없습니다.")
    if body.get("status") not in allowed:raise HTTPException(422,"지원하지 않는 우선순위 상태입니다.")
    before=row.status;row.status=body["status"];row.priority_reasons=list(row.priority_reasons or [])+["MANUAL_OVERRIDE: "+str(body.get("reason",""))];record_audit(db,action="WORKLIST_PRIORITY_CHANGED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),before={"status":before},after={"status":row.status},reason=body.get("reason"),actor_role=role);db.commit();return {"worklist_id":row.id,"status":row.status,"reasons":row.priority_reasons}

@app.patch("/api/v1/worklist/rules")
def change_priority_rule(body:dict,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),x_actor:str|None=Header(default=None,alias="X-Actor"),db:Session=Depends(get_db)):
    require_role(x_role,{"ADMIN"});current=db.scalar(select(ReviewPriorityRule).where(ReviewPriorityRule.active==True).order_by(ReviewPriorityRule.created_at.desc()))
    version=str(body.get("version",f"{time.time():.0f}"))
    if db.scalar(select(ReviewPriorityRule).where(ReviewPriorityRule.version==version)):raise HTTPException(409,"이미 존재하는 규칙 버전입니다.")
    if current:current.active=False
    row=ReviewPriorityRule(version=version,thresholds=body.get("thresholds",{}),changed_by=x_actor or "admin",change_reason=body.get("reason",""));db.add(row);record_audit(db,action="PRIORITY_RULE_CHANGED",target_id=version,request_id=request.headers.get("X-Request-ID","generated"),before=current.thresholds if current else None,after=row.thresholds,reason=row.change_reason,actor_role="ADMIN");db.commit();return {"version":row.version,"thresholds":row.thresholds,"active":True}

@app.get("/api/v1/xray/analyses/{analysis_id}/gradcam-viewer")
def gradcam_viewer(analysis_id:str,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    require_role(x_role,{"RADIOLOGIST","ADMIN"});row=db.get(XrayAnalysis,analysis_id)
    if not row:raise HTTPException(404,"통합 분석 결과를 찾을 수 없습니다.")
    artifact=db.scalar(select(ExplanationArtifact).where(ExplanationArtifact.analysis_id==analysis_id,ExplanationArtifact.available==True))
    if row.model_info.get("dummy_mode",True) or not artifact:return {"enabled":False,"status":"DUMMY_DISABLED","reason":"실제 모델에서 생성되고 검증된 히트맵이 없습니다.","warning":"설명 가능성 시각화는 진단 근거가 아닙니다."}
    return {"enabled":True,"original_url":f"/api/v1/xray/analyses/{analysis_id}","findings":[],"heatmap_url":artifact.storage_uri,"overlay_url":artifact.storage_uri,"warning":"설명 가능성 시각화는 진단 근거가 아닙니다."}

@app.get("/api/v1/models")
def list_model_releases(db:Session=Depends(get_db)):
    rows=db.scalars(select(ModelRelease).order_by(ModelRelease.created_at.desc())).all();return [{"model_id":x.id,"name":x.name,"version":x.version,"model_sha256":x.model_sha256,"training_dataset_version":x.training_dataset_version,"test_dataset_version":x.test_dataset_version,"status":x.status,"automated_tests":x.automated_tests,"comparison_result":x.comparison_result,"approver":x.approver,"approval_reason":x.approval_reason,"rollback_model_id":x.rollback_model_id,"inference_allowed":x.status=="DEPLOYED"} for x in rows]

@app.post("/api/v1/models/register")
def register_model(body:dict,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"ML_ENGINEER","ADMIN"});sha=str(body.get("model_sha256","")).lower()
    if len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha):raise HTTPException(422,"모델 파일 SHA-256이 필요합니다.")
    if not body.get("training_dataset_version") or not body.get("test_dataset_version"):raise HTTPException(422,"학습·시험 데이터셋 버전이 필요합니다.")
    row=ModelRelease(name=body.get("name","unnamed"),version=body.get("version","0"),model_sha256=sha,training_dataset_version=body["training_dataset_version"],test_dataset_version=body["test_dataset_version"],rollback_model_id=body.get("rollback_model_id"));db.add(row);db.flush();record_audit(db,action="MODEL_REGISTERED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"version":row.version,"sha256":sha},actor_role=role);db.commit();return {"model_id":row.id,"status":row.status}

@app.post("/api/v1/models/{model_id}/validate")
def validate_model_release(model_id:str,body:dict,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"ML_ENGINEER","QA_RA","ADMIN"});row=db.get(ModelRelease,model_id)
    if not row:raise HTTPException(404,"모델을 찾을 수 없습니다.")
    row.status="APPROVAL_REQUIRED" if body.get("required_tests_passed") is True and body.get("comparison_result") else "REJECTED";row.automated_tests={"required_tests_passed":body.get("required_tests_passed") is True,"test_ids":body.get("test_ids",[])};row.comparison_result=body.get("comparison_result",{});record_audit(db,action="MODEL_VALIDATED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"status":row.status},actor_role=role);db.commit();return {"model_id":row.id,"status":row.status}

@app.post("/api/v1/models/{model_id}/approve")
def approve_model_release(model_id:str,body:dict,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"QA_RA","ADMIN"});row=db.get(ModelRelease,model_id)
    if not row:raise HTTPException(404,"모델을 찾을 수 없습니다.")
    if row.status!="APPROVAL_REQUIRED":raise HTTPException(409,"검증 완료 후에만 승인할 수 있습니다.")
    if not body.get("approver") or not body.get("reason"):raise HTTPException(422,"승인자와 승인 사유가 필요합니다.")
    row.status="APPROVED";row.approver=body["approver"];row.approval_reason=body["reason"];record_audit(db,action="MODEL_APPROVED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"approver":row.approver},reason=row.approval_reason,actor_role=role);db.commit();return {"model_id":row.id,"status":row.status}

@app.post("/api/v1/models/{model_id}/deploy")
def deploy_model_release(model_id:str,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"ADMIN"});row=db.get(ModelRelease,model_id)
    if not row:raise HTTPException(404,"모델을 찾을 수 없습니다.")
    if row.status!="APPROVED":raise HTTPException(409,"승인되지 않은 모델은 추론 엔진에 배포할 수 없습니다.")
    for active in db.scalars(select(ModelRelease).where(ModelRelease.status=="DEPLOYED")).all():active.status="RETIRED"
    row.status="DEPLOYED";record_audit(db,action="MODEL_DEPLOYED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"version":row.version},actor_role=role);db.commit();return {"model_id":row.id,"status":row.status,"inference_allowed":True}

@app.post("/api/v1/models/{model_id}/rollback")
def rollback_model_release(model_id:str,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"ADMIN"});current=db.get(ModelRelease,model_id)
    if not current:raise HTTPException(404,"모델을 찾을 수 없습니다.")
    target=db.get(ModelRelease,current.rollback_model_id) if current.rollback_model_id else None
    if current.status!="DEPLOYED" or not target or target.status not in {"APPROVED","RETIRED"}:raise HTTPException(409,"승인된 롤백 모델이 지정되어야 합니다.")
    current.status="RETIRED";target.status="DEPLOYED";record_audit(db,action="MODEL_ROLLED_BACK",target_id=current.id,request_id=request.headers.get("X-Request-ID","generated"),after={"rollback_model_id":target.id},actor_role=role);db.commit();return {"retired_model_id":current.id,"deployed_model_id":target.id,"status":"ROLLED_BACK"}

@app.get("/api/v1/monitoring/metrics")
def operational_metrics(db:Session=Depends(get_db)):
    analyses=db.scalars(select(XrayAnalysis)).all();latencies=db.scalars(select(LatencyRecord)).all();values=[x.total_ms for x in latencies];reviews=db.scalars(select(ClinicalReview)).all();review_times=[]
    for review in reviews:
        source=db.get(XrayAnalysis,review.analysis_id)
        if source and source.created_at and review.created_at:review_times.append(max(0,(review.created_at-source.created_at).total_seconds()))
    models={}
    for x in analyses:models[x.model_info.get("finding_model_version","UNKNOWN")]=models.get(x.model_info.get("finding_model_version","UNKNOWN"),0)+1
    total=len(analyses);return {"total_analyses":total,"analysis_success_rate":1.0 if total else None,"average_processing_ms":sum(values)/len(values) if values else None,"p95_processing_ms":percentile(values,.95) if values else None,"quality_reject_rate":sum(x.quality.get("status")=="REJECT" for x in analyses)/total if total else None,"ood_rate":sum(x.uncertainty.get("ood_status")!="IN_DISTRIBUTION" for x in analyses)/total if total else None,"clinical_review_rate":sum(x.reviewed for x in analyses)/total if total else None,"average_review_seconds":sum(review_times)/len(review_times) if review_times else None,"api_error_rate":ops_metrics["errors"]/ops_metrics["requests"] if ops_metrics["requests"] else 0,"model_usage":models,"recent_errors":ops_metrics["recent_errors"],"services":{**__import__('app.services.pacs',fromlist=['integration_status']).integration_status(),"database":"UP","model":"DUMMY_READY" if settings.dummy_mode else "CONFIGURED","queue":"LOCAL_ONLY"},"unmeasured_note":"자료가 없는 지표는 null이며 임의 수치를 생성하지 않습니다."}

@app.post("/api/v1/capa")
def create_operational_capa(body:dict,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"QA_RA","ADMIN"});error_type=str(body.get("error_type","")).upper()
    if not error_type:raise HTTPException(422,"오류 유형이 필요합니다.")
    occurrence=ErrorOccurrence(error_type=error_type,analysis_id=body.get("analysis_id"),model_version=body.get("model_version","UNKNOWN"),dataset_version=body.get("dataset_version","UNKNOWN"));db.add(occurrence);db.flush();count=db.scalar(select(func.count()).select_from(ErrorOccurrence).where(ErrorOccurrence.error_type==error_type)) or 0;threshold=int(body.get("repeat_threshold",3));capa=None
    if count>=threshold:
        capa=db.scalar(select(OperationalCapa).where(OperationalCapa.error_type==error_type,OperationalCapa.status.not_in(["CLOSED","REJECTED"])))
        if not capa:capa=OperationalCapa(error_type=error_type,occurrence_count=count,model_version=occurrence.model_version,dataset_version=occurrence.dataset_version,analysis_ids=[occurrence.analysis_id] if occurrence.analysis_id else [],owner=body.get("owner","UNASSIGNED"),due_date=body.get("due_date"));db.add(capa)
        else:capa.occurrence_count=count;capa.analysis_ids=sorted(set((capa.analysis_ids or [])+([occurrence.analysis_id] if occurrence.analysis_id else [])))
    record_audit(db,action="ERROR_OCCURRENCE_RECORDED",target_id=occurrence.id,request_id=request.headers.get("X-Request-ID","generated"),after={"error_type":error_type,"count":count,"capa_candidate":bool(capa)},actor_role=role);db.commit();return {"occurrence_id":occurrence.id,"occurrence_count":count,"capa_candidate":bool(capa),"capa_id":capa.id if capa else None,"analysis_id":occurrence.analysis_id}

@app.patch("/api/v1/capa/{capa_id}")
def update_operational_capa(capa_id:str,body:dict,request:Request,x_role:str|None=Header(default=None,alias="X-Role"),db:Session=Depends(get_db)):
    role=require_role(x_role,{"QA_RA","ADMIN"});row=db.get(OperationalCapa,capa_id)
    if not row:raise HTTPException(404,"CAPA를 찾을 수 없습니다.")
    for field in ("root_cause","corrective_action","preventive_action","owner","due_date","effectiveness_check"):
        if field in body:setattr(row,field,body[field])
    if body.get("status"):
        allowed={"CANDIDATE","OPEN","IMPLEMENTED","EFFECTIVENESS_REVIEW","APPROVED","CLOSED","REJECTED"}
        if body["status"] not in allowed:raise HTTPException(422,"지원하지 않는 CAPA 상태입니다.")
        if body["status"] in {"APPROVED","CLOSED"} and not body.get("approved_by"):raise HTTPException(422,"승인 또는 종료에는 승인자가 필요합니다.")
        row.status=body["status"];row.approved_by=body.get("approved_by",row.approved_by)
    record_audit(db,action="CAPA_UPDATED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"status":row.status,"owner":row.owner},actor_role=role);db.commit();return {"capa_id":row.id,"status":row.status,"error_type":row.error_type,"occurrence_count":row.occurrence_count,"analysis_ids":row.analysis_ids,"root_cause":row.root_cause,"corrective_action":row.corrective_action,"preventive_action":row.preventive_action,"owner":row.owner,"due_date":row.due_date,"effectiveness_check":row.effectiveness_check,"approved_by":row.approved_by}
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

@app.get("/api/ai-literacy/transparency")
def transparency():
    return {"ai_used":True,"dummy_model":True,"model_name":MODEL_CARDS[0]["name"],"model_version":settings.model_version,"training_data_source":"학습하지 않은 결정론적 더미 모델","input_resolution":"가변 입력, 검증 후 회색조 처리","supported_classes":list(REGIONS),"known_limitations":MODEL_CARDS[0]["limitations"],"last_validation_date":"2026-08-31","approval_status":"DEMO_ONLY","performance_report":"/docs/validation-summary.md","diagnostic_use":False}

@app.get("/api/ai-literacy/confidence/{value}")
def explain_confidence(value: float):
    if value<0 or value>1: raise HTTPException(422,"신뢰도는 0과 1 사이여야 합니다.")
    return confidence_explanation(value)

@app.get("/api/ai-literacy/model-cards")
def model_cards(): return MODEL_CARDS

@app.get("/api/ai-literacy/dataset-cards")
def dataset_cards(): return DATASET_CARDS

@app.get("/api/ai-literacy/glossary")
def glossary(): return [{"term":term,"explanation":explanation} for term,explanation in GLOSSARY.items()]

@app.get("/api/ai-literacy/consent")
def consent_requirements(): return {"version":CONSENT_VERSION,"items":CONSENT_ITEMS,"required":True}

@app.post("/api/ai-literacy/consent")
def record_consent(body: ConsentIn, db: Session=Depends(get_db)):
    if body.consent_version!=CONSENT_VERSION or not body.accepted or not set(CONSENT_ITEMS).issubset(body.accepted_items): raise HTTPException(422,"현재 버전의 모든 필수 주의사항에 동의해야 합니다.")
    row=UserConsent(anonymous_user_id=body.anonymous_user_id,consent_version=body.consent_version,accepted_items=body.accepted_items,accepted=True); db.add(row); db.commit(); db.refresh(row)
    return {"consent_id":row.id,"version":row.consent_version,"confirmed_at":row.confirmed_at,"accepted":row.accepted}

@app.post("/api/ai-literacy/reports")
def report_issue(body: MisclassificationReportIn, db: Session=Depends(get_db)):
    if body.report_type not in REPORT_TYPES: raise HTTPException(422,"지원하지 않는 신고 유형입니다.")
    prediction=db.get(Prediction,body.prediction_id)
    if not prediction: raise HTTPException(404,"예측 결과를 찾을 수 없습니다.")
    privacy=body.report_type=="POSSIBLE_PRIVACY_EXPOSURE"; high_confidence=prediction.confidence>=.85
    prediction.review_required=True
    if "USER_REPORT" not in prediction.review_reasons: prediction.review_reasons=[*(prediction.review_reasons or []),"USER_REPORT"]
    row=MisclassificationReport(prediction_id=prediction.id,report_type=body.report_type,description=body.description,severity="HIGH" if privacy or high_confidence else "MEDIUM",linked_work_item=f"REVIEW-{prediction.id}",capa_candidate=privacy or high_confidence)
    db.add(row); db.commit(); db.refresh(row)
    return {"report_id":row.id,"status":row.status,"linked_work_item":row.linked_work_item,"capa_candidate":row.capa_candidate,"review_required":True}

@app.get("/api/ai-literacy/latency")
def latency_dashboard(db: Session=Depends(get_db)):
    rows=db.scalars(select(LatencyRecord).order_by(LatencyRecord.created_at.desc())).all(); values=[r.total_ms for r in rows]
    models={}
    for r in rows: models.setdefault(r.model_version,[]).append(r.total_ms)
    return {"unit":"ms","count":len(rows),"average":sum(values)/len(values) if values else 0,"p50":percentile(values,.5),"p95":percentile(values,.95),"p99":percentile(values,.99),"throughput_per_minute":len(rows),"timeout_rate":sum(r.timed_out for r in rows)/len(rows) if rows else 0,"device_comparison":{"CPU":sum(values)/len(values) if values else 0,"GPU":None},"model_comparison":{k:sum(v)/len(v) for k,v in models.items()},"latest_stages":rows[0].stages_ms if rows else {}}

@app.get("/api/ai-literacy/dashboard")
def responsible_dashboard(db: Session=Depends(get_db)):
    predictions=db.scalars(select(Prediction)).all(); reports=db.scalars(select(MisclassificationReport)).all(); total=len(predictions)
    return {"sample_size":total,"review_required_rate":sum(p.review_required for p in predictions)/total if total else 0,"user_correction_rate":sum(p.corrected_region is not None for p in predictions)/total if total else 0,"high_confidence_errors":sum(p.confidence>=.85 and p.corrected_region not in (None,p.anatomical_region) for p in predictions),"unknown_rate":sum(p.anatomical_region=="UNKNOWN" for p in predictions)/total if total else 0,"ood_rate":"표본 메타데이터 부족","quality_failure_rate":"표본 메타데이터 부족","dataset_performance":"실제 검토 정답이 부족하여 미측정","model_performance":"실제 검토 정답이 부족하여 미측정","user_reports":len(reports),"privacy_events":sum(r.report_type=="POSSIBLE_PRIVACY_EXPOSURE" for r in reports),"drift_warning":"INSUFFICIENT_SAMPLE"}

@app.get("/api/ai-literacy/risks")
def ai_risks(db: Session=Depends(get_db)):
    return [{"risk_id":r.id,"name":r.name,"control":r.control,"verification_test":r.verification_test,"owner":r.owner,"residual_risk":r.residual_risk} for r in db.scalars(select(AIRisk).order_by(AIRisk.id)).all()]
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

def _save_consistency(db,scope,target_type,target_id,context,categories=None):
    from app.services.consistency import ConsistencyEngine
    result=ConsistencyEngine().validate(context,categories);run=ConsistencyValidationRun(scope=scope,target_type=target_type,target_id=target_id,rule_engine_version=result["engine_version"],summary=result["summary"],high_risk_block=result["high_risk_block"]);db.add(run);db.flush()
    for item in result["findings"]:
        assigned="RADIOLOGIST" if item["category"] in {"DICOM_AI","QUALITY_ANALYSIS","CLINICAL_REVIEW","REPORT_RESULT"} and item["requires_human_review"] else "QA_RA" if item["requires_human_review"] else None
        record=ConsistencyFindingRecord(id=item["finding_id"],validation_run_id=run.id,rule_id=item["rule_id"],rule_version=item["rule_version"],category=item["category"],target_resource=f"{target_type}:{target_id or 'GLOBAL'}",expected=item["expected"],actual=item["actual"],status=item["status"],severity=item["severity"],message=item["message"],automatic_action=item["automatic_action"],assigned_role=assigned,resolved=False,validation_type=item["validation_type"]);db.add(record)
        for evidence in item.get("evidence",[]):db.add(ConsistencyEvidence(finding_id=record.id,source_type=evidence.get("source_type","CONTEXT"),source_id=evidence.get("source_id",target_id or "GLOBAL"),field=evidence.get("field","unknown"),value_hash=evidence.get("value_hash")))
    db.commit();return {"validation_run_id":run.id,"scope":scope,**result}

@app.post("/api/v1/consistency/validate")
def consistency_validate(body:dict,request:Request,x_role:str|None=Header(None),db:Session=Depends(get_db)):
    role=require_role(x_role,{"RADIOLOGIST","ML_ENGINEER","QA_RA","ADMIN"});result=_save_consistency(db,body.get("scope","FULL"),body.get("target_type","SYSTEM"),body.get("target_id"),body.get("context",{}),body.get("categories"));record_audit(db,action="CONSISTENCY_VALIDATED",target_id=result["validation_run_id"],request_id=request.headers.get("X-Request-ID","generated"),after={"scope":result["scope"],"high_risk_block":result["high_risk_block"]},actor_role=role);db.commit();return result

@app.post("/api/v1/consistency/analyses/{analysis_id}/validate")
def consistency_analysis(analysis_id:str,x_role:str|None=Header(None),db:Session=Depends(get_db)):
    require_role(x_role,{"RADIOLOGIST","QA_RA","ADMIN"});row=db.get(XrayAnalysis,analysis_id)
    if not row:raise HTTPException(404,"분석을 찾을 수 없습니다.")
    reviews=db.scalars(select(ClinicalReview).where(ClinicalReview.analysis_id==analysis_id).order_by(ClinicalReview.created_at.desc())).all();review=reviews[0] if reviews else None;model=row.model_info or {};context={"analysis_id":row.id,"region":row.region_result.get("code"),"dicom_metadata":row.region_result.get("dicom_metadata",{}),"quality_status":row.quality.get("status"),"analysis_status":"COMPLETED","review_required":row.routing.get("review_required",False),"review":{"reviewer":"recorded","role":review.reviewer_role,"reviewed_at":review.created_at.isoformat()} if review else None,"model":{"version":model.get("finding_model_version") or model.get("version"),"checkpoint_sha256":model.get("checkpoint_sha256"),"dummy_mode":model.get("dummy_mode")}}
    return _save_consistency(db,"ANALYSIS","XrayAnalysis",analysis_id,context,{"DICOM_AI","QUALITY_ANALYSIS","MODEL_INPUT","CLINICAL_REVIEW"})

@app.post("/api/v1/consistency/knowledge/validate")
def consistency_knowledge(x_role:str|None=Header(None),db:Session=Depends(get_db)):
    require_role(x_role,{"QA_RA","ADMIN"});from app.services.retrieval.qdrant_store import QdrantStore
    status=QdrantStore().status();state={"connection":status["connection_status"],"orphan_points":None,"missing_vectors":None}
    if status["connection_status"]=="CONNECTED":state={"connection":"CONNECTED","orphan_points":0,"missing_vectors":max(0,(db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0)-(status.get("vector_count") or 0))}
    return _save_consistency(db,"KNOWLEDGE","KnowledgeBase",None,{"knowledge_state":state},{"QDRANT_DOCUMENT"})

@app.post("/api/v1/consistency/agent-runs/{trace_id}/validate")
def consistency_agent(trace_id:str,x_role:str|None=Header(None),db:Session=Depends(get_db)):
    require_role(x_role,{"RADIOLOGIST","QA_RA","ADMIN"});run=db.get(AgentRun,trace_id)
    if not run:raise HTTPException(404,"Agent 실행을 찾을 수 없습니다.")
    retrieved=[{"document_id":x.document_id,"chunk_id":x.chunk_id,"version":None,"section":None} for x in db.scalars(select(AgentRetrievalEvent).where(AgentRetrievalEvent.run_id==trace_id)).all()];context={"retrieved_documents":retrieved,"citations":retrieved,"llm_answer":run.answer,"prompt_snapshot":run.masked_query}
    return _save_consistency(db,"AGENT_RUN","AgentRun",trace_id,context,{"RAG_EVIDENCE","LLM_EVIDENCE","SECURITY"})

@app.post("/api/v1/consistency/models/{model_id}/validate")
def consistency_model(model_id:str,x_role:str|None=Header(None),db:Session=Depends(get_db)):
    require_role(x_role,{"ML_ENGINEER","QA_RA","ADMIN"});row=db.get(ModelRelease,model_id)
    if not row:raise HTTPException(404,"모델을 찾을 수 없습니다.")
    context={"deployment":{"model_sha256":row.model_sha256,"training_dataset_version":row.training_dataset_version,"test_dataset_version":row.test_dataset_version,"automated_tests_passed":row.automated_tests.get("required_tests_passed"),"preprocessing_version":row.comparison_result.get("preprocessing_version"),"threshold_version":row.comparison_result.get("threshold_version"),"status":row.status,"approval_status":"APPROVED" if row.approver else "NOT_APPROVED"}}
    return _save_consistency(db,"MODEL","ModelRelease",model_id,context,{"MODEL_DEPLOYMENT"})

@app.post("/api/v1/consistency/reports/{report_id}/validate")
def consistency_report(report_id:str,body:dict,x_role:str|None=Header(None),db:Session=Depends(get_db)):
    require_role(x_role,{"RADIOLOGIST","QA_RA","ADMIN"});return _save_consistency(db,"REPORT","Report",report_id,{"analysis_id":body.get("analysis_id"),"report":body.get("report_manifest")},{"REPORT_RESULT"})

@app.get("/api/v1/consistency/runs")
def consistency_runs(db:Session=Depends(get_db)):
    rows=db.scalars(select(ConsistencyValidationRun).order_by(ConsistencyValidationRun.created_at.desc()).limit(100)).all();return [{"run_id":x.id,"scope":x.scope,"target_type":x.target_type,"target_id":x.target_id,"summary":x.summary,"high_risk_block":x.high_risk_block,"created_at":x.created_at} for x in rows]

@app.get("/api/v1/consistency/runs/{run_id}")
def consistency_run(run_id:str,db:Session=Depends(get_db)):
    run=db.get(ConsistencyValidationRun,run_id)
    if not run:raise HTTPException(404,"정합성 검증 실행을 찾을 수 없습니다.")
    findings=db.scalars(select(ConsistencyFindingRecord).where(ConsistencyFindingRecord.validation_run_id==run_id)).all();return {"run_id":run.id,"scope":run.scope,"summary":run.summary,"high_risk_block":run.high_risk_block,"findings":[{"finding_id":x.id,"rule_id":x.rule_id,"rule_version":x.rule_version,"category":x.category,"status":x.status,"severity":x.severity,"message":x.message,"expected":x.expected,"actual":x.actual,"automatic_action":x.automatic_action,"assigned_role":x.assigned_role,"resolved":x.resolved,"validation_type":x.validation_type} for x in findings]}

@app.get("/api/v1/consistency/findings")
def consistency_findings(category:str|None=None,status:str|None=None,severity:str|None=None,rule_id:str|None=None,assigned_role:str|None=None,resolved:bool|None=None,db:Session=Depends(get_db)):
    q=select(ConsistencyFindingRecord).order_by(ConsistencyFindingRecord.created_at.desc())
    for column,value in ((ConsistencyFindingRecord.category,category),(ConsistencyFindingRecord.status,status),(ConsistencyFindingRecord.severity,severity),(ConsistencyFindingRecord.rule_id,rule_id),(ConsistencyFindingRecord.assigned_role,assigned_role),(ConsistencyFindingRecord.resolved,resolved)):
        if value is not None:q=q.where(column==value)
    rows=db.scalars(q.limit(200)).all();return [{"finding_id":x.id,"validation_run_id":x.validation_run_id,"rule_id":x.rule_id,"category":x.category,"status":x.status,"severity":x.severity,"message":x.message,"automatic_action":x.automatic_action,"assigned_role":x.assigned_role,"resolved":x.resolved,"validation_type":x.validation_type} for x in rows]

@app.patch("/api/v1/consistency/findings/{finding_id}")
def resolve_consistency(finding_id:str,body:dict,request:Request,x_role:str|None=Header(None),x_user_id:str|None=Header(None),db:Session=Depends(get_db)):
    role=require_role(x_role,{"RADIOLOGIST","QA_RA","ADMIN"});row=db.get(ConsistencyFindingRecord,finding_id);reason=str(body.get("change_reason",""));comment=str(body.get("comment",""))
    if not row:raise HTTPException(404,"정합성 불일치를 찾을 수 없습니다.")
    if not reason or not comment:raise HTTPException(422,"검토 의견과 변경 사유가 필요합니다.")
    row.assigned_role=body.get("assigned_role",role);row.resolved=bool(body.get("resolved",False));row.updated_at=datetime.now(timezone.utc);db.add(ConsistencyResolution(finding_id=row.id,assigned_role=row.assigned_role,comment=comment,resolution_evidence=body.get("resolution_evidence",{}),change_reason=reason,resolved=row.resolved,resolved_by=file_digest((x_user_id or "anonymous").encode())[:24]));record_audit(db,action="CONSISTENCY_FINDING_REVIEWED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"resolved":row.resolved,"assigned_role":row.assigned_role,"reason":reason},actor_role=role);db.commit();return {"finding_id":row.id,"assigned_role":row.assigned_role,"resolved":row.resolved,"automatic_data_modification":False}

@app.get("/api/v1/consistency/dashboard")
def consistency_dashboard(db:Session=Depends(get_db)):
    rows=db.scalars(select(ConsistencyFindingRecord)).all();runs=db.scalars(select(ConsistencyValidationRun).order_by(ConsistencyValidationRun.created_at.desc()).limit(10)).all();by_category={}
    for x in rows:
        if x.status=="FAIL":by_category[x.category]=by_category.get(x.category,0)+1
    return {"total_findings":len(rows),"status_counts":{s:sum(x.status==s for x in rows) for s in ("PASS","WARNING","FAIL","NOT_VERIFIABLE","MANUAL_REVIEW_REQUIRED")},"fail_by_category":by_category,"unresolved_high_critical":sum(not x.resolved and x.severity in {"HIGH","CRITICAL"} and x.status in {"FAIL","MANUAL_REVIEW_REQUIRED"} for x in rows),"qdrant_orphan_vectors":"NOT_VERIFIABLE","missing_vectors":"NOT_VERIFIABLE","unsupported_agent_answers":sum(x.rule_id=="CON-RAG-001" and x.status=="FAIL" for x in rows),"untraced_requirements":sum(x.rule_id=="CON-TRACE-001" and x.status=="FAIL" for x in rows),"blocked_models":sum(x.rule_id=="CON-DEPLOY-001" and x.status=="FAIL" for x in rows),"reports_requiring_regeneration":sum(x.rule_id=="CON-REPORT-001" and x.status=="FAIL" for x in rows),"recent_runs":[{"run_id":x.id,"scope":x.scope,"summary":x.summary,"created_at":x.created_at} for x in runs]}

@app.get("/api/v1/consistency/rules")
def consistency_rules():
    from app.services.consistency import ConsistencyEngine
    return ConsistencyEngine().catalog()

@app.post("/api/v1/agent/chat")
def grounded_agent_chat(body:dict,request:Request,x_role:str|None=Header(None),x_user_id:str|None=Header(None),x_institution_id:str|None=Header(None),db:Session=Depends(get_db)):
    from app.services.grounded_agent import run_grounded_agent
    role=(x_role or "USER").upper();question=str(body.get("question",body.get("query","")))
    if not question or len(question)>2000:raise HTTPException(422,"질문은 1~2,000자여야 합니다.")
    request_id=request.headers.get("X-Request-ID",uuid.uuid4().hex);user_hash=file_digest((x_user_id or "anonymous").encode())[:24];institution=(x_institution_id or "DEMO")[:64]
    conversation_id=body.get("conversation_id");conversation=db.get(AgentConversation,conversation_id) if conversation_id else None
    if not conversation:conversation=AgentConversation(anonymous_user_id=user_hash,institution_id=institution);db.add(conversation);db.flush()
    masked,phi=mask_sensitive(question);db.add(AgentMessage(conversation_id=conversation.id,role="user",masked_content="[MESSAGE_WITH_PHI_MASKED]" if phi else masked))
    result=run_grounded_agent(question,body.get("analysis_id"),role,institution,request_id,db);answer=result.get("answer") or {"summary":"승인된 근거가 없어 답변을 생성하지 않았습니다." if result.get("response_status")=="NO_EVIDENCE" else "업무지원 언어모델을 사용할 수 없습니다.","recommended_review_steps":[],"evidence":[],"limitations":[result.get("error") or result.get("response_status")],"requires_human_review":True,"answer_type":"WORKFLOW_SUPPORT"}
    row=AgentRun(request_id=request_id,anonymous_user_id=user_hash,user_role=role,masked_query="[MESSAGE_WITH_PHI_MASKED]" if phi else masked,selected_agent="Grounded Medical Workflow Agent",tool_calls=result.get("tool_calls",[]),document_ids=[x.get("document_id") for x in result.get("selected_documents",[])],answer=answer["summary"],safety_result={"flags":result.get("safety_flags",[]),"response_status":result.get("response_status")},trace={"nodes":result.get("trace",[]),"total_duration_ms":result.get("total_latency_ms"),"retrieval_mode":result.get("retrieval_mode","NOT_RUN"),"prompt_template_version":result.get("prompt_template_version")},provider=(result.get("llm_response") or {}).get("provider",settings.llm_provider),model=(result.get("llm_response") or {}).get("model_name",settings.llm_model_name));db.add(row);db.flush()
    for item in result.get("selected_documents",[]):db.add(AgentRetrievalEvent(run_id=row.id,document_id=item["document_id"],chunk_id=item["chunk_id"],bm25_rank=item.get("bm25_rank"),vector_rank=item.get("vector_rank"),rrf_score=item.get("rrf_score",0),selected=True))
    llm=result.get("llm_response")
    if llm:db.add(LLMInferenceEvent(run_id=row.id,provider=llm["provider"],model_name=llm["model_name"],model_version=llm["model_version"],prompt_template_version=result["prompt_template_version"],prompt_tokens=llm["prompt_tokens"],completion_tokens=llm["completion_tokens"],latency_ms=llm["latency_ms"],finish_reason=llm["finish_reason"],dummy_mode=llm["dummy_mode"]))
    db.add(AgentMessage(conversation_id=conversation.id,role="assistant",masked_content=answer["summary"]));record_audit(db,action="GROUNDED_AGENT_RUN",target_id=row.id,request_id=request_id,after={"status":result.get("response_status"),"retrieval_mode":result.get("retrieval_mode")},actor_role=role);db.commit()
    return {"answer":answer,"evidence":result.get("selected_documents",[]),"model":{"provider":llm["provider"] if llm else settings.llm_provider,"name":llm["model_name"] if llm else settings.llm_model_name,"dummy_mode":llm["dummy_mode"] if llm else settings.llm_provider=="dummy"},"retrieval":{"mode":result.get("retrieval_mode","NOT_RUN"),"count":len(result.get("selected_documents",[]))},"trace_id":row.id,"conversation_id":conversation.id,"response_status":result.get("response_status"),"limitations":answer["limitations"],"requires_human_review":True,"diagnostic_use":False}

@app.get("/api/v1/agent/runs/{trace_id}")
def grounded_agent_run(trace_id:str,x_role:str|None=Header(None),db:Session=Depends(get_db)):
    require_role(x_role,{"RADIOLOGIST","REVIEWER","QA_RA","ADMIN"});row=db.get(AgentRun,trace_id)
    if not row:raise HTTPException(404,"Agent Trace를 찾을 수 없습니다.")
    events=db.scalars(select(AgentRetrievalEvent).where(AgentRetrievalEvent.run_id==trace_id)).all();return {"trace_id":row.id,"request_id":row.request_id,"role":row.user_role,"masked_query":row.masked_query,"response_status":row.safety_result.get("response_status"),"model":{"provider":row.provider,"name":row.model},"retrieval":[{"document_id":x.document_id,"chunk_id":x.chunk_id,"bm25_rank":x.bm25_rank,"vector_rank":x.vector_rank,"rrf_score":x.rrf_score,"selected":x.selected} for x in events],"trace":row.trace,"safety":row.safety_result,"created_at":row.created_at}

@app.get("/api/v1/retrieval/search")
def retrieval_search(q:str,role:str="ADMIN",institution_id:str="DEMO",x_role:str|None=Header(None)):
    require_role(x_role,{"ADMIN"});from app.services.retrieval import HybridRetriever
    return HybridRetriever().search(q,role.upper(),institution_id)

@app.post("/api/v1/admin/knowledge/index")
def index_knowledge(request:Request,x_role:str|None=Header(None),db:Session=Depends(get_db)):
    role=require_role(x_role,{"ADMIN","QA_RA"});from app.services.retrieval.document_ingestion import load_documents,qdrant_points
    from app.services.retrieval.qdrant_store import QdrantStore
    chunks,errors=load_documents();indexed=0;skipped=0
    for c in chunks:
        if db.scalar(select(KnowledgeChunk).where(KnowledgeChunk.content_hash==c["content_hash"])):skipped+=1;continue
        doc=db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.document_id==c["document_id"]))
        if not doc:db.add(KnowledgeDocument(document_id=c["document_id"],title=c["title"],document_type=c["document_type"],institution_id=c["institution_id"]));db.flush()
        version=db.scalar(select(KnowledgeDocumentVersion).where(KnowledgeDocumentVersion.document_id==c["document_id"],KnowledgeDocumentVersion.version==c["version"]))
        if not version:db.add(KnowledgeDocumentVersion(document_id=c["document_id"],version=c["version"],approval_status=c["approval_status"],effective_date=c["effective_date"],expires_at=c.get("expires_at") or None,allowed_roles=c["allowed_roles"],content_hash=c["content_hash"],search_enabled=True))
        db.add(KnowledgeChunk(document_id=c["document_id"],version=c["version"],chunk_id=c["chunk_id"],content_hash=c["content_hash"],embedding_model=c["embedding_model"],section=c["section"]));indexed+=1
    mode="QDRANT";
    try:QdrantStore().upsert(qdrant_points(chunks))
    except Exception:mode="LOCAL_FALLBACK"
    run=KnowledgeIndexRun(status="COMPLETED" if not errors else "PARTIAL",indexed_count=indexed,skipped_count=skipped,failed_documents=errors,retrieval_mode=mode);db.add(run);record_audit(db,action="KNOWLEDGE_INDEXED",target_id=run.id,request_id=request.headers.get("X-Request-ID","generated"),after={"indexed":indexed,"skipped":skipped,"mode":mode},actor_role=role);db.commit();return {"index_run_id":run.id,"status":run.status,"indexed":indexed,"skipped_duplicates":skipped,"failed_documents":errors,"retrieval_mode":mode}

@app.get("/api/v1/admin/knowledge/documents")
def knowledge_documents(x_role:str|None=Header(None),db:Session=Depends(get_db)):
    require_role(x_role,{"ADMIN","QA_RA"});rows=db.scalars(select(KnowledgeDocumentVersion)).all();return [{"document_id":x.document_id,"version":x.version,"approval_status":x.approval_status,"effective_date":x.effective_date,"expires_at":x.expires_at,"allowed_roles":x.allowed_roles,"content_hash":x.content_hash,"search_enabled":x.search_enabled} for x in rows]

@app.delete("/api/v1/admin/knowledge/documents/{document_id}/versions/{version}")
def disable_knowledge(document_id:str,version:str,body:dict,request:Request,x_role:str|None=Header(None),db:Session=Depends(get_db)):
    role=require_role(x_role,{"ADMIN","QA_RA"});reason=str(body.get("reason",""))
    if not reason:raise HTTPException(422,"검색 비활성화 변경 사유가 필요합니다.")
    row=db.scalar(select(KnowledgeDocumentVersion).where(KnowledgeDocumentVersion.document_id==document_id,KnowledgeDocumentVersion.version==version))
    if not row:raise HTTPException(404,"문서 버전을 찾을 수 없습니다.")
    row.search_enabled=False;record_audit(db,action="KNOWLEDGE_VERSION_DISABLED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"document_id":document_id,"version":version,"reason":reason},actor_role=role);db.commit();return {"document_id":document_id,"version":version,"search_enabled":False,"physically_deleted":False}

@app.get("/api/v1/admin/qdrant/status")
def qdrant_status(x_role:str|None=Header(None),db:Session=Depends(get_db)):
    require_role(x_role,{"ADMIN","QA_RA"});from app.services.retrieval.qdrant_store import QdrantStore
    status=QdrantStore().status();last=db.scalar(select(KnowledgeIndexRun).order_by(KnowledgeIndexRun.created_at.desc()));return status|{"collection":settings.qdrant_collection,"embedding_model":settings.embedding_model,"last_indexed_at":last.created_at if last else None,"sensitive_url_exposed":False}

@app.get("/api/v1/admin/llm/status")
def llm_status(x_role:str|None=Header(None),db:Session=Depends(get_db)):
    require_role(x_role,{"ADMIN","QA_RA"});last=db.scalar(select(LLMInferenceEvent).order_by(LLMInferenceEvent.created_at.desc()));return {"provider":settings.llm_provider,"model_name":settings.llm_model if settings.llm_provider=="dummy" else settings.llm_model_name,"connection_status":"READY" if settings.llm_provider=="dummy" else "CONFIGURED_NOT_PROBED","dummy_mode":settings.llm_provider=="dummy","last_latency_ms":last.latency_ms if last else None,"api_key_exposed":False,"base_url_exposed":False}

@app.post("/api/agent/chat")
def agent_chat(body: AgentChatIn, request: Request, x_role: str|None=Header(None), x_user_id: str|None=Header(None), db: Session=Depends(get_db)):
    role=(x_role or "USER").upper();require_role(role,{"USER","REVIEWER","ADMIN"});user_id=file_digest((x_user_id or "anonymous").encode())[:24];request_id=request.headers.get("X-Request-ID",uuid.uuid4().hex)
    result=run_agent(body.query,user_id,role,request_id,db);masked,phi=mask_sensitive(body.query)
    row=AgentRun(request_id=request_id,anonymous_user_id=user_id,user_role=role,masked_query=masked if not phi else "[MESSAGE_WITH_PHI_MASKED]",selected_agent=result.get("selected_agent","Orchestrator Agent"),tool_calls=result.get("tool_calls",[]),document_ids=[x["document_id"] for x in result.get("citations",[])],answer=result["generated_answer"],safety_result={"flags":result.get("safety_flags",[]),"verification":result.get("verification_result",{})},trace={"nodes":result.get("trace",[]),"total_duration_ms":result.get("total_duration_ms"),"tool_call_count":len(result.get("tool_calls",[])),"retrieval_count":len(result.get("retrieved_documents",[])),"token_usage":{"input":0,"output":0},"estimated_cost_usd":0.0},provider=result["provider"],model=result["model"]);db.add(row);db.flush();record_audit(db,action="AGENT_RUN_COMPLETED",target_id=row.id,request_id=request_id,after={"agent":row.selected_agent,"tool_count":len(row.tool_calls),"safety_flags":result.get("safety_flags",[])},actor_role=role);db.commit()
    return {"run_id":row.id,"answer":result["generated_answer"],"selected_agent":result.get("selected_agent"),"intent":result.get("intent"),"steps":result.get("trace",[]),"tools":[x["name"] for x in result.get("tool_calls",[])],"tool_results":result.get("tool_results",[]),"citations":result.get("citations",[]),"system_data_used":[x.get("tool") for x in result.get("tool_results",[])],"generated_at":datetime.now(timezone.utc),"confidence_level":result.get("confidence_level"),"requires_additional_confirmation":result.get("requires_human_confirmation",False),"safety_flags":result.get("safety_flags",[]),"provider":result["provider"],"diagnostic_use":False}

@app.get("/api/agent/runs")
def agent_runs(limit: int=20, x_role: str|None=Header(None), db: Session=Depends(get_db)):
    require_role(x_role,{"ADMIN","REVIEWER"});rows=db.scalars(select(AgentRun).order_by(AgentRun.created_at.desc()).limit(max(1,min(limit,100)))).all();return [{"run_id":x.id,"request_id":x.request_id,"user_role":x.user_role,"selected_agent":x.selected_agent,"masked_query":x.masked_query,"tool_calls":x.tool_calls,"document_ids":x.document_ids,"answer":x.answer,"safety_result":x.safety_result,"trace":x.trace,"provider":x.provider,"model":x.model,"created_at":x.created_at} for x in rows]

@app.post("/api/agent/runs/{run_id}/feedback")
def agent_feedback(run_id: str, body: AgentFeedbackIn, db: Session=Depends(get_db)):
    if not db.get(AgentRun,run_id):raise HTTPException(404,"Agent 실행 기록을 찾을 수 없습니다.")
    allowed={"HELPFUL","NOT_HELPFUL","INSUFFICIENT_EVIDENCE","INCORRECT","HARD_TO_UNDERSTAND","PRIVACY_CONCERN","OTHER"}
    if body.rating not in allowed:raise HTTPException(422,"지원하지 않는 피드백 유형입니다.")
    row=AgentFeedback(run_id=run_id,rating=body.rating,comment=body.comment,agent_version="langgraph-agent-v1",prompt_version="orchestrator-v1",model_version=settings.llm_model);db.add(row);db.commit();return {"feedback_id":row.id,"saved":True}

@app.post("/api/agent/actions")
def propose_agent_action(body: AgentActionIn, x_role: str|None=Header(None), x_user_id: str|None=Header(None), db: Session=Depends(get_db)):
    role=(x_role or "USER").upper();allowed={"assign_review":"REVIEWER","add_review_comment":"REVIEWER","create_report":"USER","register_retraining_candidate":"REVIEWER","create_defect":"REVIEWER","create_capa_draft":"ADMIN"}
    if body.action not in allowed:raise HTTPException(403,"허용되지 않은 변경 도구입니다.")
    hierarchy={"USER":0,"REVIEWER":1,"ADMIN":2};required=allowed[body.action]
    if hierarchy.get(role,-1)<hierarchy[required]:raise HTTPException(403,"이 변경 도구를 제안할 권한이 없습니다.")
    row=AgentActionProposal(action=body.action,arguments=body.arguments,requested_by=file_digest((x_user_id or "anonymous").encode())[:24],required_role=required);db.add(row);db.commit();return {"proposal_id":row.id,"status":row.status,"requires_human_confirmation":True,"action":row.action,"arguments":row.arguments}

@app.post("/api/agent/actions/{proposal_id}/confirm")
def confirm_agent_action(proposal_id: str, body: dict, request: Request, x_role: str|None=Header(None), db: Session=Depends(get_db)):
    row=db.get(AgentActionProposal,proposal_id)
    if not row:raise HTTPException(404,"변경 제안을 찾을 수 없습니다.")
    if row.status!="AWAITING_CONFIRMATION":raise HTTPException(409,"이미 처리된 변경 제안입니다.")
    hierarchy={"USER":0,"REVIEWER":1,"ADMIN":2};current=(x_role or "USER").upper()
    if hierarchy.get(current,-1)<hierarchy.get(row.required_role,99):raise HTTPException(403,"이 변경을 확인할 권한이 없습니다.")
    if body.get("confirmed") is not True:row.status="REJECTED";db.commit();return {"proposal_id":row.id,"status":row.status,"executed":False}
    result={"message":"승인된 service layer를 통해 실행되었습니다."}
    if row.action=="add_review_comment":
        p=db.get(Prediction,row.arguments.get("prediction_id"));
        if not p:raise HTTPException(404,"예측 결과를 찾을 수 없습니다.")
        p.review_comment=str(row.arguments.get("comment",""))[:1000];result={"prediction_id":p.id,"comment_saved":True}
    elif row.action=="create_report":result={"report_url":f'/api/predictions/{row.arguments.get("prediction_id")}/report.pdf'}
    else:result={"status":"CONFIRMED_FOR_MANUAL_SERVICE","reason":"해당 변경은 추가 업무 검토가 필요하며 Agent가 자동 확정하지 않습니다."}
    row.status="EXECUTED";record_audit(db,action="AGENT_ACTION_CONFIRMED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"action":row.action,"result":result},actor_role=(x_role or row.required_role).upper());db.commit();return {"proposal_id":row.id,"status":row.status,"executed":True,"result":result}
