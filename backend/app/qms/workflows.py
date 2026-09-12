"""Change and CAPA workflows reuse stored test evidence; no automatic approval."""
from fastapi import Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models as legacy
from app.db.qms_models import ChangeRequest, ImpactAssessment
from app.services.qms_integrity import canonical
from app.services.qms_validation import validate_text
from .router import router, access, WRITE, Strict, ApprovalInput, get, out, save, approve_gate

class ChangeInput(Strict):
    change_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=5000)
    reason: str = Field(min_length=3, max_length=1000)
    affected_components: list[str] = Field(default_factory=list, max_length=100)
    affected_requirements: list[str] = Field(default_factory=list, max_length=100)
    affected_risks: list[str] = Field(default_factory=list, max_length=100)
    affected_tests: list[str] = Field(default_factory=list, max_length=100)
    affected_models: list[str] = Field(default_factory=list, max_length=100)
    affected_datasets: list[str] = Field(default_factory=list, max_length=100)
    affected_integrations: list[str] = Field(default_factory=list, max_length=100)

class TransitionInput(Strict):
    expected_status: str = Field(min_length=3,max_length=32)
    target_status: str = Field(min_length=3,max_length=32)
    reason: str = Field(min_length=3,max_length=1000)

@router.post('/change-requests/{change_id}/transition')
def change_transition(change_id: str,body: TransitionInput,p=Depends(access(WRITE)),db: Session=Depends(get_db)):
    row=get(db,ChangeRequest,change_id)
    allowed={'PROPOSED':{'IMPACT_ANALYSIS','CANCELLED'},'IMPACT_ANALYSIS':{'CANCELLED'},
        'REVIEW_REQUIRED':{'REJECTED','CANCELLED'},'APPROVED':{'IMPLEMENTING'},'IMPLEMENTING':{'VERIFICATION_REQUIRED'}}
    if body.expected_status!=row.status or body.target_status not in allowed.get(row.status,set()):
        raise HTTPException(409,detail={'code':'STATE_CONFLICT'})
    validate_text(body.reason); row.status=body.target_status
    return save(db,row,p,'CHANGE_TRANSITIONED')

def validate_targets(db, body):
    for field, model in [('affected_requirements', legacy.TestRequirement), ('affected_risks', legacy.AIRisk),
        ('affected_tests', legacy.TestScenario), ('affected_models', legacy.ModelRelease), ('affected_datasets', legacy.DatasetVersion)]:
        for key in getattr(body, field): get(db, model, key)

@router.post('/change-requests', status_code=201)
def create_change(body: ChangeInput, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    validate_text(canonical(body.model_dump())); validate_targets(db, body)
    return save(db, ChangeRequest(**body.model_dump(), requested_by=p.subject), p, 'CHANGE_CREATED')

@router.get('/change-requests')
def changes(p=Depends(access()), db: Session=Depends(get_db)):
    return [out(r) for r in db.scalars(select(ChangeRequest))]

@router.get('/change-requests/{change_id}')
def change(change_id: str, p=Depends(access()), db: Session=Depends(get_db)):
    row = get(db, ChangeRequest, change_id)
    return {**out(row), 'assessments': [out(a) for a in db.scalars(select(ImpactAssessment).where(ImpactAssessment.change_request_id==row.id))]}

@router.patch('/change-requests/{change_id}')
def edit_change(change_id: str, body: ChangeInput, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    row = get(db, ChangeRequest, change_id)
    if row.status != 'PROPOSED': raise HTTPException(409, detail={'code': 'STATE_CONFLICT'})
    if row.change_id != body.change_id: raise HTTPException(409, detail={'code': 'IDENTIFIER_IMMUTABLE'})
    validate_text(canonical(body.model_dump())); validate_targets(db, body)
    for k,v in body.model_dump().items(): setattr(row,k,v)
    return save(db,row,p,'CHANGE_UPDATED')

class AssessmentInput(Strict):
    assessment_type: str = Field(min_length=3,max_length=64)
    impact_level: str = Field(pattern='^(LOW|MEDIUM|HIGH)$')
    affected_items: list[str] = Field(max_length=100)
    regression_scope: list[str] = Field(min_length=1,max_length=100)
    new_risks: list[str] = Field(default_factory=list,max_length=100)
    regulatory_impact: str = Field(min_length=3,max_length=2000)
    cybersecurity_impact: str = Field(min_length=3,max_length=2000)
    privacy_impact: str = Field(min_length=3,max_length=2000)
    interoperability_impact: str = Field(min_length=3,max_length=2000)

@router.post('/change-requests/{change_id}/impact-assessment')
def assess(change_id: str, body: AssessmentInput, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    row = get(db,ChangeRequest,change_id)
    if row.status not in {'PROPOSED','IMPACT_ANALYSIS'}: raise HTTPException(409,detail={'code':'STATE_CONFLICT'})
    validate_text(canonical(body.model_dump()))
    if body.impact_level=='HIGH' and 'FULL_REGRESSION' not in body.regression_scope:
        raise HTTPException(422,detail={'code':'FULL_REGRESSION_REQUIRED'})
    for key in body.regression_scope:
        if key!='FULL_REGRESSION': get(db,legacy.TestScenario,key)
    for key in body.new_risks: get(db,legacy.AIRisk,key)
    db.add(ImpactAssessment(change_request_id=row.id,**body.model_dump(),assessed_by=p.subject))
    row.status='REVIEW_REQUIRED'; row.impact_summary=body.impact_level
    return save(db,row,p,'CHANGE_IMPACT_ASSESSED')

@router.post('/change-requests/{change_id}/approve')
def approve_change(change_id: str, body: ApprovalInput,p=Depends(access({'QA_RA'})),db: Session=Depends(get_db)):
    row=get(db,ChangeRequest,change_id)
    if row.status!='REVIEW_REQUIRED': raise HTTPException(409,detail={'code':'STATE_CONFLICT'})
    approve_gate(row,p,body,row.requested_by,1)

def passing_tests(db, scenario_ids):
    if not scenario_ids: return False
    for key in scenario_ids:
        if db.get(legacy.TestScenario,key) is None: return False
        row=db.scalar(select(legacy.TestExecution).where(legacy.TestExecution.scenario_id==key).order_by(legacy.TestExecution.executed_at.desc(),legacy.TestExecution.id.desc()).limit(1))
        if row is None or row.status!='PASS': return False
        if db.scalar(select(legacy.TestEvidence).where(legacy.TestEvidence.execution_id==row.id,legacy.TestEvidence.storage_status!='METADATA_ONLY')) is None:
            return False
    return True

@router.post('/change-requests/{change_id}/verify')
def verify_change(change_id: str,p=Depends(access({'QA_RA'})),db: Session=Depends(get_db)):
    row=get(db,ChangeRequest,change_id)
    if row.status!='VERIFICATION_REQUIRED': raise HTTPException(409,detail={'code':'STATE_CONFLICT'})
    if not passing_tests(db,row.affected_tests): raise HTTPException(409,detail={'code':'REGRESSION_EVIDENCE_REQUIRED'})
    row.status='VERIFIED'; return save(db,row,p,'CHANGE_VERIFIED')

@router.post('/change-requests/{change_id}/release')
def release_change(change_id: str,body: ApprovalInput,p=Depends(access({'ADMIN'})),db: Session=Depends(get_db)):
    row=get(db,ChangeRequest,change_id)
    if row.status!='VERIFIED': raise HTTPException(409,detail={'code':'STATE_CONFLICT'})
    approve_gate(row,p,body,row.requested_by,1)

class CapaInput(Strict):
    error_type: str = Field(pattern=r'^[A-Z_]{3,64}$')
    severity: str = Field(pattern='^(LOW|MEDIUM|HIGH|CRITICAL)$')
    owner: str = Field(pattern=r'^[A-Za-z0-9._-]{3,64}$')
    defect_ids: list[str] = Field(default_factory=list,max_length=50)
    change_ids: list[str] = Field(default_factory=list,max_length=50)
    model_ids: list[str] = Field(default_factory=list,max_length=50)
    test_ids: list[str] = Field(default_factory=list,max_length=100)

@router.post('/capas',status_code=201)
def create_capa(body: CapaInput,p=Depends(access({'QA_RA'})),db: Session=Depends(get_db)):
    for attr,model in [('defect_ids',legacy.DefectRecord),('change_ids',ChangeRequest),('model_ids',legacy.ModelRelease),('test_ids',legacy.TestScenario)]:
        for key in getattr(body,attr): get(db,model,key)
    data=body.model_dump(exclude={'error_type','owner'})
    data.update(version=1,created_by=p.subject,qms_managed=True)
    return save(db,legacy.OperationalCapa(error_type=body.error_type,owner=body.owner,qms_data=data),p,'CAPA_CREATED')

@router.get('/capas')
def capas(p=Depends(access()),db: Session=Depends(get_db)):
    return [{**out(r),'source_type':'OPERATIONAL'} for r in db.scalars(select(legacy.OperationalCapa))] + [
        {**out(r),'source_type':'LEGACY','editable':False} for r in db.scalars(select(legacy.Capa))]

@router.get('/capas/{capa_id}')
def capa(capa_id: str,p=Depends(access()),db: Session=Depends(get_db)):
    row=db.get(legacy.OperationalCapa,capa_id) or db.get(legacy.Capa,capa_id)
    if not row: raise HTTPException(404,detail={'code':'RESOURCE_NOT_FOUND'})
    return out(row)

class CapaAction(Strict):
    reason: str = Field(min_length=3,max_length=1000)
    root_cause: str = Field(default='',max_length=3000)
    corrective_action: str = Field(default='',max_length=3000)
    preventive_action: str = Field(default='',max_length=3000)
    effectiveness_check: str = Field(default='',max_length=3000)

def managed_capa(db,key):
    row=get(db,legacy.OperationalCapa,key)
    if not row.qms_data.get('qms_managed'): raise HTTPException(409,detail={'code':'LEGACY_CAPA_REQUIRES_MIGRATION_REVIEW'})
    return row

@router.post('/capas/{capa_id}/transition')
def capa_transition(capa_id: str,body: TransitionInput,p=Depends(access({'QA_RA'})),db: Session=Depends(get_db)):
    row=managed_capa(db,capa_id)
    allowed={'CANDIDATE':{'INVESTIGATION','REJECTED'},'ACTION_PLANNED':{'IMPLEMENTING'},
        'IMPLEMENTING':{'EFFECTIVENESS_CHECK'},'CLOSED':{'REOPENED'},'REOPENED':{'INVESTIGATION'}}
    if row.status!=body.expected_status or body.target_status not in allowed.get(row.status,set()):
        raise HTTPException(409,detail={'code':'STATE_CONFLICT'})
    validate_text(body.reason);row.status=body.target_status
    return save(db,row,p,'CAPA_TRANSITIONED')

@router.patch('/capas/{capa_id}')
def start_capa(capa_id: str,body: CapaAction,p=Depends(access({'QA_RA'})),db: Session=Depends(get_db)):
    row=managed_capa(db,capa_id)
    if row.status not in {'CANDIDATE','REOPENED'}: raise HTTPException(409,detail={'code':'STATE_CONFLICT'})
    validate_text(canonical(body.model_dump())); row.status='INVESTIGATION'
    return save(db,row,p,'CAPA_INVESTIGATION_STARTED')

@router.post('/capas/{capa_id}/root-cause')
def root_cause(capa_id: str,body: CapaAction,p=Depends(access({'QA_RA'})),db: Session=Depends(get_db)):
    row=managed_capa(db,capa_id)
    if row.status!='INVESTIGATION': raise HTTPException(409,detail={'code':'STATE_CONFLICT'})
    if not body.root_cause.strip(): raise HTTPException(422,detail={'code':'ROOT_CAUSE_REQUIRED'})
    validate_text(canonical(body.model_dump())); row.root_cause=body.root_cause; row.status='ROOT_CAUSE_ANALYSIS'
    return save(db,row,p,'CAPA_ROOT_CAUSE_RECORDED')

@router.post('/capas/{capa_id}/action-plan')
def action_plan(capa_id: str,body: CapaAction,p=Depends(access({'QA_RA'})),db: Session=Depends(get_db)):
    row=managed_capa(db,capa_id)
    if row.status!='ROOT_CAUSE_ANALYSIS': raise HTTPException(409,detail={'code':'STATE_CONFLICT'})
    if not body.corrective_action.strip() or not body.preventive_action.strip(): raise HTTPException(422,detail={'code':'ACTIONS_REQUIRED'})
    validate_text(canonical(body.model_dump())); row.corrective_action=body.corrective_action; row.preventive_action=body.preventive_action; row.status='ACTION_PLANNED'
    return save(db,row,p,'CAPA_ACTION_PLANNED')

@router.post('/capas/{capa_id}/effectiveness-check')
def effectiveness(capa_id: str,body: CapaAction,p=Depends(access({'QA_RA'})),db: Session=Depends(get_db)):
    row=managed_capa(db,capa_id)
    if row.status not in {'ACTION_PLANNED','IMPLEMENTING','EFFECTIVENESS_CHECK'}: raise HTTPException(409,detail={'code':'STATE_CONFLICT'})
    if p.subject==row.owner: raise HTTPException(409,detail={'code':'SEPARATION_OF_DUTIES_REQUIRED'})
    if not body.effectiveness_check.strip() or not passing_tests(db,row.qms_data.get('test_ids',[])):
        raise HTTPException(409,detail={'code':'EFFECTIVENESS_EVIDENCE_REQUIRED'})
    for key in row.qms_data.get('change_ids',[]):
        if get(db,ChangeRequest,key).status!='RELEASED': raise HTTPException(409,detail={'code':'CHANGE_NOT_RELEASED'})
    validate_text(body.effectiveness_check); row.effectiveness_check=body.effectiveness_check; row.status='APPROVAL_REQUIRED'
    return save(db,row,p,'CAPA_EFFECTIVENESS_RECORDED')

@router.post('/capas/{capa_id}/close')
def close_capa(capa_id: str,body: ApprovalInput,p=Depends(access({'QA_RA'})),db: Session=Depends(get_db)):
    row=managed_capa(db,capa_id)
    if row.status!='APPROVAL_REQUIRED': raise HTTPException(409,detail={'code':'STATE_CONFLICT'})
    approve_gate(row,p,body,row.owner,row.qms_data.get('version',1))

def release_gate(db,model_id):
    from app.services.qms_integrity import verify_chain
    from .validation import guard_critical
    guard_critical(db)
    reasons=[]
    if any(r.residual_risk=='CRITICAL' and r.qms_data and r.qms_data.get('status')!='APPROVED' for r in db.scalars(select(legacy.AIRisk))):
        reasons.append('QMS_CRITICAL_RISK_UNRESOLVED')
    for row in db.scalars(select(ChangeRequest)):
        if model_id in row.affected_models and row.status not in {'RELEASED','CANCELLED','REJECTED'}: reasons.append('QMS_UNRELEASED_CHANGE')
    for row in db.scalars(select(legacy.OperationalCapa)):
        if row.qms_data.get('severity') in {'HIGH','CRITICAL'} and row.status not in {'CLOSED','REJECTED'} and model_id in row.qms_data.get('model_ids',[]): reasons.append('QMS_OPEN_CAPA')
    if verify_chain(db)['status']=='INTEGRITY_FAILED': reasons.append('QMS_AUDIT_INTEGRITY_FAILED')
    if reasons: raise HTTPException(409,detail={'code':'QMS_RELEASE_BLOCK','reasons':sorted(set(reasons))})

@router.get('/tests')
def tests(p=Depends(access()),db: Session=Depends(get_db)):
    return {'scenarios':[out(r) for r in db.scalars(select(legacy.TestScenario))],
        'executions':[out(r) for r in db.scalars(select(legacy.TestExecution))],
        'evidence':[out(r) for r in db.scalars(select(legacy.TestEvidence))]}

@router.get('/defects')
def defects(p=Depends(access()),db: Session=Depends(get_db)):
    return [out(r) for r in db.scalars(select(legacy.DefectRecord))]

class DefectInput(Strict):
    execution_id: str = Field(min_length=1,max_length=36)
    summary: str = Field(min_length=3,max_length=300)
    severity: str = Field(pattern='^(LOW|MEDIUM|HIGH|CRITICAL)$')

@router.post('/defects',status_code=201)
def create_defect(body: DefectInput,p=Depends(access({'QA_RA'})),db: Session=Depends(get_db)):
    execution=get(db,legacy.TestExecution,body.execution_id)
    if execution.status!='FAIL': raise HTTPException(409,detail={'code':'FAILED_EXECUTION_REQUIRED'})
    validate_text(body.summary)
    return save(db,legacy.DefectRecord(execution_id=body.execution_id,summary=body.summary,
        qms_data={'severity':body.severity,'created_by':p.subject,'version':1}),p,'DEFECT_CREATED')
