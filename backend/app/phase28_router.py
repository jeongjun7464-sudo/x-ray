from datetime import datetime,timezone
import hashlib,json,re,uuid
from fastapi import APIRouter,Depends,File,Header,HTTPException,Request,UploadFile
from fastapi.responses import Response
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from app.core.auth import current_principal
from app.core.config import settings
from app.db.database import get_db
from app.db.models import (AuditEvent,ConsistencyValidationRun,DatasetVersion,DeploymentRecord,DriftEvaluation,ModelApproval,ModelArtifact,ModelInferenceBinding,ModelRelease,ModelTransitionEvent,ModelValidationMetric,ModelValidationRun,ReleaseBlockDecision,ValidationPolicy)
from app.services.audit import record_audit
from app.services.dataset_lineage_validation import validate_lineage
from app.services.model_artifact_validation import validate_artifact
from app.services.model_deployment import deployment_contract
from app.services.model_validation_runner import VALIDATION_TYPES,evaluate_metrics,validation_status

router=APIRouter(prefix="/api/v1",tags=["Phase 28 ModelOps"])

def require_validation_adapter():
    """Fail closed until measurements originate from a configured runner."""
    raise HTTPException(409,detail={"code":"VALIDATION_RUNNER_NOT_CONFIGURED","status":"NOT_MEASURED","message":"서버측 검증 실행기가 연결되지 않아 승인 가능한 검증 근거를 생성할 수 없습니다."})
TRANSITIONS={"DRAFT":{"REGISTERED"},"REGISTERED":{"ARTIFACT_VERIFIED","REJECTED"},"ARTIFACT_VERIFIED":{"VALIDATION_PENDING"},"VALIDATION_PENDING":{"VALIDATING"},"VALIDATING":{"VALIDATION_FAILED","APPROVAL_REQUIRED"},"VALIDATION_FAILED":{"VALIDATION_PENDING","REJECTED"},"APPROVAL_REQUIRED":{"APPROVED","REJECTED"},"APPROVED":{"DEPLOYMENT_PENDING","RETIRED"},"DEPLOYMENT_PENDING":{"DEPLOYED","APPROVED"},"DEPLOYED":{"SUSPENDED"},"SUSPENDED":{"ROLLED_BACK"},"ROLLED_BACK":{"RETIRED"}}

def actor(role_header,actor_header,allowed):
    principal=current_principal();role=principal.role if principal else ((role_header or "USER").upper() if settings.auth_allow_legacy_headers and not settings.auth_enforced else "USER");subject=principal.subject if principal else (actor_header or "legacy-user")
    if role not in allowed:raise HTTPException(403,detail={"code":"AUTHORIZATION_DENIED"})
    return role,subject
def transition(db,row,to_status,role,subject,reason,request):
    old=row.status
    if to_status not in TRANSITIONS.get(old,set()):raise HTTPException(409,detail={"code":"INVALID_MODEL_STATUS_TRANSITION","from":old,"to":to_status})
    row.status=to_status;db.add(ModelTransitionEvent(model_release_id=row.id,from_status=old,to_status=to_status,actor_id=subject,actor_role=role,reason=reason,request_id=request.headers.get("X-Request-ID","generated")))
def release_out(x):return {"model_release_id":x.id,"name":x.name,"version":x.version,"status":x.status,"checkpoint_sha256":None if x.status in {"DRAFT","REGISTERED"} else x.model_sha256,"training_dataset_version":x.training_dataset_version,"test_dataset_version":x.test_dataset_version,"registered_by":x.registered_by,"approved_by":x.approved_by,"deployed_by":x.deployed_by,"specification":x.specification,"inference_allowed":x.status=="DEPLOYED"}

@router.post("/model-releases",status_code=201)
def create_release(body:dict,request:Request,x_role:str|None=Header(None,alias="X-Role"),x_actor:str|None=Header(None,alias="X-Actor"),db:Session=Depends(get_db)):
    role,subject=actor(x_role,x_actor,{"ML_ENGINEER"});required=("name","version","architecture","framework","model_format","training_dataset_version","test_dataset_version","intended_use","prohibited_use","input_specification","output_specification","preprocessing_version","threshold_version")
    missing=[x for x in required if not body.get(x)]
    if missing:raise HTTPException(422,detail={"code":"REQUIRED_FIELDS_MISSING","fields":missing})
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}",str(body["name"])) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,31}",str(body["version"])):raise HTTPException(422,detail={"code":"INVALID_NAME_OR_VERSION"})
    if body["training_dataset_version"]==body["test_dataset_version"]:raise HTTPException(422,detail={"code":"TRAIN_TEST_DATASET_MUST_DIFFER"})
    if db.scalar(select(ModelRelease).where(ModelRelease.name==body["name"],ModelRelease.version==body["version"])):raise HTTPException(409,detail={"code":"DUPLICATE_MODEL_VERSION"})
    versions={x.version for x in db.scalars(select(DatasetVersion)).all()}
    if body["training_dataset_version"] not in versions or body["test_dataset_version"] not in versions:raise HTTPException(422,detail={"code":"DATASET_VERSION_NOT_FOUND"})
    spec={k:body[k] for k in required if k not in {"name","version","training_dataset_version","test_dataset_version"}}
    provisional=hashlib.sha256(f"UNVERIFIED:{body['name']}:{body['version']}:{uuid.uuid4()}".encode()).hexdigest();row=ModelRelease(name=body["name"],version=body["version"],model_sha256=provisional,training_dataset_version=body["training_dataset_version"],test_dataset_version=body["test_dataset_version"],status="DRAFT",specification=spec,registered_by=subject);db.add(row);db.flush();transition(db,row,"REGISTERED",role,subject,"model metadata registered",request);record_audit(db,action="MODEL_RELEASE_REGISTERED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"name":row.name,"version":row.version},actor_id=subject,actor_role=role);db.commit();return release_out(row)

@router.get("/model-releases")
def releases(db:Session=Depends(get_db)):return [release_out(x) for x in db.scalars(select(ModelRelease).order_by(ModelRelease.created_at.desc())).all()]
@router.get("/model-releases/{release_id}")
def release_detail(release_id:str,db:Session=Depends(get_db)):
    row=db.get(ModelRelease,release_id)
    if not row:raise HTTPException(404,detail={"code":"MODEL_RELEASE_NOT_FOUND"})
    data=release_out(row);data["artifacts"]=[{"artifact_id":x.id,"filename":x.filename,"sha256":x.sha256,"status":x.signature_status,"malware_scan_status":x.malware_scan_status} for x in db.scalars(select(ModelArtifact).where(ModelArtifact.model_release_id==row.id)).all()];return data

@router.post("/model-releases/{release_id}/artifact")
async def artifact(release_id:str,request:Request,file:UploadFile=File(...),declared_sha256:str|None=Header(None,alias="X-Artifact-SHA256"),x_role:str|None=Header(None,alias="X-Role"),x_actor:str|None=Header(None,alias="X-Actor"),db:Session=Depends(get_db)):
    role,subject=actor(x_role,x_actor,{"ML_ENGINEER"});row=db.get(ModelRelease,release_id)
    if not row:raise HTTPException(404,detail={"code":"MODEL_RELEASE_NOT_FOUND"})
    if row.status!="REGISTERED":raise HTTPException(409,detail={"code":"INVALID_MODEL_STATUS_TRANSITION"})
    data=await file.read();result=validate_artifact(file.filename or "",data,declared_sha256)
    if result["status"]=="FAILED":raise HTTPException(422,detail=result)
    if db.scalar(select(ModelArtifact).where(ModelArtifact.sha256==result["sha256"])):raise HTTPException(409,detail={"code":"DUPLICATE_ARTIFACT"})
    item=ModelArtifact(model_release_id=row.id,filename=file.filename,format=result["format"],size_bytes=result["size_bytes"],sha256=result["sha256"],storage_uri=None,storage_status="METADATA_ONLY",malware_scan_status=result["malware_scan_status"],signature_status=result["status"]);db.add(item);row.model_sha256=result["sha256"]
    if result["status"]=="VERIFIED":transition(db,row,"ARTIFACT_VERIFIED",role,subject,"artifact signature and hash verified",request)
    record_audit(db,action="MODEL_ARTIFACT_INSPECTED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"sha256":result["sha256"],"status":result["status"]},actor_id=subject,actor_role=role);db.commit();return {"artifact_id":item.id,"storage_status":item.storage_status,**result}

@router.post("/validation-policies",status_code=201)
def policy_create(body:dict,x_role:str|None=Header(None,alias="X-Role"),x_actor:str|None=Header(None,alias="X-Actor"),db:Session=Depends(get_db)):
    _,subject=actor(x_role,x_actor,{"ML_ENGINEER"});row=ValidationPolicy(policy_id=body.get("policy_id","default"),version=body.get("version","1.0"),target_region=body.get("target_region"),target_finding=body.get("target_finding"),metric_thresholds=body.get("metric_thresholds",{}),minimum_sample_size=max(1,int(body.get("minimum_sample_size",30))),robustness_thresholds=body.get("robustness_thresholds",{}),fairness_thresholds=body.get("fairness_thresholds",{}),latency_thresholds=body.get("latency_thresholds",{}),created_by=subject);db.add(row);db.commit();return {"id":row.id,"status":"DRAFT","active":False}
@router.patch("/validation-policies/{policy_id}")
def policy_update(policy_id:str,body:dict,x_role:str|None=Header(None,alias="X-Role"),x_actor:str|None=Header(None,alias="X-Actor"),db:Session=Depends(get_db)):
    role,subject=actor(x_role,x_actor,{"QA_RA","ADMIN"});row=db.get(ValidationPolicy,policy_id)
    if not row:raise HTTPException(404,detail={"code":"POLICY_NOT_FOUND"})
    if role=="QA_RA":
        if row.created_by==subject:raise HTTPException(409,detail={"code":"INDEPENDENT_POLICY_APPROVAL_REQUIRED"})
        row.approved_by=subject;row.approved_at=datetime.now(timezone.utc)
    if role=="ADMIN" and body.get("active") is True:
        if not row.approved_by:raise HTTPException(409,detail={"code":"POLICY_APPROVAL_REQUIRED"})
        for old in db.scalars(select(ValidationPolicy).where(ValidationPolicy.active==True)).all():old.active=False
        row.active=True
    db.commit();return {"id":row.id,"approved_by":row.approved_by,"active":row.active}
@router.get("/validation-policies")
def policy_list(db:Session=Depends(get_db)):return [{"id":x.id,"policy_id":x.policy_id,"version":x.version,"active":x.active,"approved_by":x.approved_by,"minimum_sample_size":x.minimum_sample_size,"metric_thresholds":x.metric_thresholds} for x in db.scalars(select(ValidationPolicy)).all()]
@router.get("/validation-policies/{policy_id}")
def policy_get(policy_id:str,db:Session=Depends(get_db)):
    row=db.get(ValidationPolicy,policy_id)
    if not row:raise HTTPException(404,detail={"code":"POLICY_NOT_FOUND"})
    return {"id":row.id,"policy_id":row.policy_id,"version":row.version,"active":row.active,"approved_by":row.approved_by,"minimum_sample_size":row.minimum_sample_size,"metric_thresholds":row.metric_thresholds}

@router.post("/model-releases/{release_id}/validate",status_code=201)
def validate(release_id:str,body:dict,request:Request,idempotency_key:str|None=Header(None,alias="Idempotency-Key"),x_role:str|None=Header(None,alias="X-Role"),x_actor:str|None=Header(None,alias="X-Actor"),db:Session=Depends(get_db)):
    actor(x_role,x_actor,{"ML_ENGINEER","QA_RA"})
    require_validation_adapter()
    role,subject=actor(x_role,x_actor,{"ML_ENGINEER","QA_RA"});row=db.get(ModelRelease,release_id)
    if not row:raise HTTPException(404,detail={"code":"MODEL_RELEASE_NOT_FOUND"})
    if not idempotency_key:raise HTTPException(422,detail={"code":"IDEMPOTENCY_KEY_REQUIRED"})
    old=db.scalar(select(ModelValidationRun).where(ModelValidationRun.idempotency_key==idempotency_key))
    if old:return {"validation_run_id":old.id,"status":old.status,"idempotent_replay":True}
    if row.status!="ARTIFACT_VERIFIED":raise HTTPException(409,detail={"code":"ARTIFACT_VERIFICATION_REQUIRED"})
    policy=db.get(ValidationPolicy,body.get("policy_id")) if body.get("policy_id") else db.scalar(select(ValidationPolicy).where(ValidationPolicy.active==True))
    if not policy or not policy.approved_by:raise HTTPException(409,detail={"code":"APPROVED_VALIDATION_POLICY_REQUIRED"})
    train=db.scalar(select(DatasetVersion).where(DatasetVersion.version==row.training_dataset_version));test=db.scalar(select(DatasetVersion).where(DatasetVersion.version==row.test_dataset_version));lineage=validate_lineage({"manifest":train.manifest} if train else {},{"manifest":test.manifest} if test else {})
    if lineage["status"]!="VERIFIED":raise HTTPException(409,detail=lineage)
    transition(db,row,"VALIDATION_PENDING",role,subject,"validation requested",request);transition(db,row,"VALIDATING",role,subject,"validation started",request)
    kind=str(body.get("validation_type","FUNCTIONAL")).upper()
    if kind not in VALIDATION_TYPES:raise HTTPException(422,detail={"code":"VALIDATION_TYPE_NOT_ALLOWED"})
    run=ModelValidationRun(model_release_id=row.id,dataset_version=row.test_dataset_version,status="VALIDATING",validation_type=kind,environment=body.get("environment","LOCAL_DEMO"),seed=int(body.get("seed",42)),requested_by=subject,idempotency_key=idempotency_key,policy_id=policy.id);db.add(run);db.flush();metrics=evaluate_metrics(body.get("measurements",[]),policy.metric_thresholds,policy.minimum_sample_size)
    for item in metrics:db.add(ModelValidationMetric(validation_run_id=run.id,metric_name=item["metric_name"],anatomical_region=item.get("anatomical_region"),finding_code=item.get("finding_code"),subgroup=item.get("subgroup"),value=item.get("value"),threshold=item.get("threshold"),passed=item.get("passed"),sample_size=item["sample_size"],status=item["status"]))
    result=validation_status(metrics);run.status="PASSED" if result=="APPROVAL_REQUIRED" else "FAILED";run.completed_at=datetime.now(timezone.utc);transition(db,row,result,role,subject,"validation completed",request);record_audit(db,action="MODEL_VALIDATION_COMPLETED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"run_id":run.id,"status":run.status,"lineage":lineage},actor_id=subject,actor_role=role);db.commit();return {"validation_run_id":run.id,"status":run.status,"model_status":row.status,"metrics":metrics,"lineage":lineage,"performance_claim":False}

@router.get("/model-validation-runs")
def runs(status:str|None=None,model_release_id:str|None=None,db:Session=Depends(get_db)):
    q=select(ModelValidationRun)
    if status:q=q.where(ModelValidationRun.status==status)
    if model_release_id:q=q.where(ModelValidationRun.model_release_id==model_release_id)
    return [{"validation_run_id":x.id,"model_release_id":x.model_release_id,"status":x.status,"validation_type":x.validation_type,"dataset_version":x.dataset_version} for x in db.scalars(q.order_by(ModelValidationRun.started_at.desc())).all()]
@router.get("/model-validation-runs/{run_id}")
def run_get(run_id:str,db:Session=Depends(get_db)):
    row=db.get(ModelValidationRun,run_id)
    if not row:raise HTTPException(404,detail={"code":"VALIDATION_RUN_NOT_FOUND"})
    metrics=db.scalars(select(ModelValidationMetric).where(ModelValidationMetric.validation_run_id==row.id)).all();return {"validation_run_id":row.id,"status":row.status,"validation_type":row.validation_type,"environment":row.environment,"seed":row.seed,"dataset_version":row.dataset_version,"policy_id":row.policy_id,"metrics":[{"metric_name":x.metric_name,"value":x.value,"threshold":x.threshold,"sample_size":x.sample_size,"status":x.status,"passed":x.passed} for x in metrics]}
@router.post("/model-validation-runs/{run_id}/cancel")
def cancel(run_id:str,body:dict,x_role:str|None=Header(None,alias="X-Role"),x_actor:str|None=Header(None,alias="X-Actor"),db:Session=Depends(get_db)):
    actor(x_role,x_actor,{"ML_ENGINEER","QA_RA"});row=db.get(ModelValidationRun,run_id)
    if not row:raise HTTPException(404,detail={"code":"VALIDATION_RUN_NOT_FOUND"})
    if row.status not in {"PENDING","VALIDATING"}:raise HTTPException(409,detail={"code":"VALIDATION_NOT_CANCELLABLE"})
    if not body.get("reason"):raise HTTPException(422,detail={"code":"CANCELLATION_REASON_REQUIRED"})
    row.status="CANCELLED";row.error_message=body["reason"];row.completed_at=datetime.now(timezone.utc);db.commit();return {"validation_run_id":row.id,"status":row.status}
@router.post("/model-validation-runs/{run_id}/retest",status_code=201)
def retest(run_id:str,body:dict,request:Request,idempotency_key:str|None=Header(None,alias="Idempotency-Key"),x_role:str|None=Header(None,alias="X-Role"),x_actor:str|None=Header(None,alias="X-Actor"),db:Session=Depends(get_db)):
    actor(x_role,x_actor,{"ML_ENGINEER","QA_RA"})
    require_validation_adapter()
    role,subject=actor(x_role,x_actor,{"ML_ENGINEER","QA_RA"});previous=db.get(ModelValidationRun,run_id)
    if not previous:raise HTTPException(404,detail={"code":"VALIDATION_RUN_NOT_FOUND"})
    if previous.status!="FAILED":raise HTTPException(409,detail={"code":"ONLY_FAILED_RUN_CAN_BE_RETESTED"})
    if not idempotency_key:raise HTTPException(422,detail={"code":"IDEMPOTENCY_KEY_REQUIRED"})
    release=db.get(ModelRelease,previous.model_release_id);policy=db.get(ValidationPolicy,previous.policy_id)
    transition(db,release,"VALIDATION_PENDING",role,subject,"failed validation retest",request);transition(db,release,"VALIDATING",role,subject,"retest started",request)
    metrics=evaluate_metrics(body.get("measurements",[]),policy.metric_thresholds,policy.minimum_sample_size);result=validation_status(metrics);new=ModelValidationRun(model_release_id=release.id,dataset_version=previous.dataset_version,status="PASSED" if result=="APPROVAL_REQUIRED" else "FAILED",validation_type=previous.validation_type,environment=body.get("environment",previous.environment),seed=int(body.get("seed",previous.seed)),requested_by=subject,idempotency_key=idempotency_key,policy_id=policy.id,retest_of=previous.id,completed_at=datetime.now(timezone.utc));db.add(new);db.flush()
    for item in metrics:db.add(ModelValidationMetric(validation_run_id=new.id,metric_name=item["metric_name"],value=item.get("value"),threshold=item.get("threshold"),passed=item.get("passed"),sample_size=item["sample_size"],status=item["status"]))
    transition(db,release,result,role,subject,"retest completed",request);db.commit();return {"validation_run_id":new.id,"retest_of":previous.id,"status":new.status,"model_status":release.status,"metrics":metrics}
@router.get("/model-validation-runs/{run_id}/report")
def report(run_id:str,db:Session=Depends(get_db)):
    data=run_get(run_id,db);text="# 익명 모델 검증 보고서\n\n"+json.dumps(data,ensure_ascii=False,indent=2)+"\n\n임상 또는 규제기관 승인을 의미하지 않습니다.\n";digest=hashlib.sha256(text.encode()).hexdigest();return Response(text+f"\nSHA-256: {digest}\n",media_type="text/markdown",headers={"X-Content-SHA256":digest})

@router.post("/model-releases/{release_id}/request-approval")
def request_approval(release_id:str,body:dict,request:Request,x_role:str|None=Header(None,alias="X-Role"),x_actor:str|None=Header(None,alias="X-Actor"),db:Session=Depends(get_db)):
    role,subject=actor(x_role,x_actor,{"ML_ENGINEER"});row=db.get(ModelRelease,release_id)
    if not row:raise HTTPException(404,detail={"code":"MODEL_RELEASE_NOT_FOUND"})
    if row.status!="APPROVAL_REQUIRED":raise HTTPException(409,detail={"code":"VALIDATION_NOT_PASSED"})
    return {"model_release_id":row.id,"status":row.status,"human_approval_required":True,"requested_by":subject}
@router.post("/model-releases/{release_id}/approve")
def approve(release_id:str,body:dict,request:Request,x_role:str|None=Header(None,alias="X-Role"),x_actor:str|None=Header(None,alias="X-Actor"),db:Session=Depends(get_db)):
    actor(x_role,x_actor,{"QA_RA"})
    require_validation_adapter()
    role,subject=actor(x_role,x_actor,{"QA_RA"});row=db.get(ModelRelease,release_id)
    if not row:raise HTTPException(404,detail={"code":"MODEL_RELEASE_NOT_FOUND"})
    if row.registered_by==subject:raise HTTPException(409,detail={"code":"REGISTERER_APPROVER_SEPARATION_REQUIRED"})
    reason=body.get("reason");validation_run_id=body.get("validation_run_id");consistency_run_id=body.get("consistency_run_id")
    if not reason or not validation_run_id or not consistency_run_id:raise HTTPException(422,detail={"code":"APPROVAL_EVIDENCE_REQUIRED"})
    run=db.get(ModelValidationRun,validation_run_id);consistency=db.get(ConsistencyValidationRun,consistency_run_id)
    if not run or run.model_release_id!=row.id or run.status!="PASSED" or not consistency or consistency.high_risk_block:raise HTTPException(409,detail={"code":"APPROVAL_EVIDENCE_INVALID"})
    transition(db,row,"APPROVED",role,subject,reason,request);row.approved_by=subject;row.approver=subject;row.approval_reason=reason;approval=ModelApproval(model_release_id=row.id,decision="APPROVED",approver_id=subject,approver_role=role,reason=reason,validation_run_id=run.id,consistency_run_id=consistency.id,monitoring_gate_id=body.get("monitoring_gate_id"),signature_meaning="내부 모델 검증 근거를 검토했으며 규제기관 또는 임상 승인을 의미하지 않음");db.add(approval);record_audit(db,action="MODEL_RELEASE_APPROVED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"approval_id":approval.id},reason=reason,actor_id=subject,actor_role=role);db.commit();return {"model_release_id":row.id,"status":row.status,"approval_id":approval.id,"regulatory_approval":False}
@router.post("/model-releases/{release_id}/reject")
def reject(release_id:str,body:dict,request:Request,x_role:str|None=Header(None,alias="X-Role"),x_actor:str|None=Header(None,alias="X-Actor"),db:Session=Depends(get_db)):
    role,subject=actor(x_role,x_actor,{"QA_RA"});row=db.get(ModelRelease,release_id)
    if not row:raise HTTPException(404,detail={"code":"MODEL_RELEASE_NOT_FOUND"})
    if not body.get("reason"):raise HTTPException(422,detail={"code":"REJECTION_REASON_REQUIRED"})
    transition(db,row,"REJECTED",role,subject,body["reason"],request);db.add(ModelApproval(model_release_id=row.id,decision="REJECTED",approver_id=subject,approver_role=role,reason=body["reason"],signature_meaning="내부 검증 거절"));db.commit();return {"model_release_id":row.id,"status":row.status}

@router.post("/model-releases/{release_id}/deploy")
def deploy(release_id:str,body:dict,request:Request,x_role:str|None=Header(None,alias="X-Role"),x_actor:str|None=Header(None,alias="X-Actor"),db:Session=Depends(get_db)):
    actor(x_role,x_actor,{"ADMIN"})
    from app.qms.workflows import release_gate
    release_gate(db,release_id)
    require_validation_adapter()
    role,subject=actor(x_role,x_actor,{"ADMIN"});row=db.get(ModelRelease,release_id)
    if not row:raise HTTPException(404,detail={"code":"MODEL_RELEASE_NOT_FOUND"})
    if row.status!="APPROVED":raise HTTPException(409,detail={"code":"MODEL_NOT_APPROVED"})
    if row.approved_by==subject:raise HTTPException(409,detail={"code":"APPROVER_DEPLOYER_SEPARATION_REQUIRED"})
    reason=body.get("reason");rollback_id=body.get("rollback_model_release_id") or row.rollback_model_id
    if not reason or not rollback_id:raise HTTPException(422,detail={"code":"DEPLOYMENT_REASON_AND_ROLLBACK_REQUIRED"})
    rollback=db.get(ModelRelease,rollback_id)
    if not rollback or rollback.status not in {"APPROVED","DEPLOYED","RETIRED","ROLLED_BACK"}:raise HTTPException(409,detail={"code":"ROLLBACK_TARGET_INVALID"})
    gate=db.scalar(select(ReleaseBlockDecision).where(ReleaseBlockDecision.release_id==row.id).order_by(ReleaseBlockDecision.evaluated_at.desc()))
    if not gate or gate.blocked:raise HTTPException(409,detail={"code":"RELEASE_GATE_BLOCKED_OR_MISSING","reason_codes":gate.reason_codes if gate else ["GATE_MISSING"]})
    if body.get("environment","LOCAL_DEMO").upper() not in {"LOCAL_DEMO","DEMO","TEST"}:raise HTTPException(409,detail={"code":"PRODUCTION_REAUTHENTICATION_NOT_CONFIGURED"})
    try:contract=deployment_contract(body.get("strategy","MANUAL"),body.get("environment","LOCAL_DEMO"),float(body.get("traffic_percentage",10)))
    except ValueError as exc:raise HTTPException(422,detail={"code":"INVALID_DEPLOYMENT_STRATEGY","message":str(exc)})
    transition(db,row,"DEPLOYMENT_PENDING",role,subject,reason,request);transition(db,row,"DEPLOYED",role,subject,reason,request);row.deployed_by=subject;row.rollback_model_id=rollback.id
    for binding in db.scalars(select(ModelInferenceBinding).where(ModelInferenceBinding.environment==body.get("environment","LOCAL_DEMO"),ModelInferenceBinding.active==True)).all():binding.active=False
    binding=ModelInferenceBinding(environment=body.get("environment","LOCAL_DEMO"),model_release_id=row.id,active=True,traffic_percentage=contract["traffic_percentage"],updated_by=subject);record=DeploymentRecord(model_release_id=row.id,environment=binding.environment,deployment_strategy=contract["strategy"],previous_model_release_id=rollback.id,status=contract["execution_status"],deployed_by=subject,completed_at=datetime.now(timezone.utc),rollback_available=True,release_gate_result={"blocked":False,"decision_id":gate.id});db.add_all([binding,record]);record_audit(db,action="MODEL_RELEASE_DEPLOYED",target_id=row.id,request_id=request.headers.get("X-Request-ID","generated"),after={"deployment_id":record.id,"contract":contract},reason=reason,actor_id=subject,actor_role=role);db.commit();return {"deployment_id":record.id,"status":record.status,"model_version":row.version,"previous_model_version":rollback.version,"rollback_available":True,"release_gate_result":{"blocked":False},**contract}

@router.post("/deployments/{deployment_id}/rollback")
def rollback(deployment_id:str,body:dict,request:Request,x_role:str|None=Header(None,alias="X-Role"),x_actor:str|None=Header(None,alias="X-Actor"),db:Session=Depends(get_db)):
    role,subject=actor(x_role,x_actor,{"ADMIN"});deployment=db.get(DeploymentRecord,deployment_id)
    if not deployment:raise HTTPException(404,detail={"code":"DEPLOYMENT_NOT_FOUND"})
    if body.get("confirmation") is not True or not body.get("reason") or not (body.get("incident_id") or body.get("alert_id")):raise HTTPException(422,detail={"code":"ROLLBACK_CONFIRMATION_EVIDENCE_REQUIRED"})
    current=db.get(ModelRelease,deployment.model_release_id);target=db.get(ModelRelease,body.get("target_model_release_id"))
    artifact=db.scalar(select(ModelArtifact).where(ModelArtifact.model_release_id==getattr(target,"id",None),ModelArtifact.signature_status=="VERIFIED"))
    if not target or target.status not in {"APPROVED","RETIRED","ROLLED_BACK","DEPLOYED"} or not artifact or artifact.sha256!=target.model_sha256:raise HTTPException(409,detail={"code":"ROLLBACK_TARGET_INTEGRITY_FAILED","safe_mode":"MANUAL_REVIEW"})
    if current.status=="DEPLOYED":transition(db,current,"SUSPENDED",role,subject,body["reason"],request);transition(db,current,"ROLLED_BACK",role,subject,body["reason"],request)
    for binding in db.scalars(select(ModelInferenceBinding).where(ModelInferenceBinding.environment==deployment.environment,ModelInferenceBinding.active==True)).all():binding.active=False
    db.add(ModelInferenceBinding(environment=deployment.environment,model_release_id=target.id,active=True,traffic_percentage=100,updated_by=subject));deployment.status="ROLLED_BACK";deployment.rollback_reason=body["reason"];record_audit(db,action="MODEL_DEPLOYMENT_ROLLED_BACK",target_id=deployment.id,request_id=request.headers.get("X-Request-ID","generated"),after={"target_model_release_id":target.id,"incident_id":body.get("incident_id"),"alert_id":body.get("alert_id")},reason=body["reason"],actor_id=subject,actor_role=role);db.commit();return {"deployment_id":deployment.id,"status":"ROLLED_BACK","active_model_release_id":target.id,"safe_mode":False}
