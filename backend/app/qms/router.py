"""QMS authoring and review APIs. Approvals fail closed without reauthentication."""
import uuid
from pathlib import Path
from types import SimpleNamespace
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, inspect, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.auth import current_principal
from app.db.database import get_db
from app.db import models as legacy
from app.db.qms_models import (ControlledDocument, ControlledDocumentVersion, DocumentReview,
    ElectronicApproval, TraceabilityLink, ChangeRequest, ImpactAssessment, AuditChainEntry)
from app.services.audit import record_audit
from app.services.qms_integrity import canonical, digest, verify_chain
from app.services.qms_validation import validate_text, ambiguity
from app.services.qms_generation import generate_draft
from app.services.electronic_approval import require_electronic_approval

router = APIRouter(prefix='/api/v1/qms', tags=['QMS'])
READ = {'ML_ENGINEER', 'QA_RA', 'ADMIN', 'RADIOLOGIST', 'TECHNICIAN', 'ADJUDICATOR'}
WRITE = {'ML_ENGINEER', 'QA_RA'}
def access(roles=READ):
    def dependency():
        p = current_principal()
        if p is None: raise HTTPException(401, detail={'code': 'AUTHENTICATION_REQUIRED'})
        if p.role not in roles: raise HTTPException(403, detail={'code': 'AUTHORIZATION_DENIED'})
        return p
    return dependency

def out(row):
    result = {c.key: getattr(row, c.key) for c in inspect(row).mapper.column_attrs}
    if 'qms_data' in result: result.update(result.pop('qms_data') or {})
    return result

def get(db, model, key):
    row = db.get(model, key)
    if row is None: raise HTTPException(404, detail={'code': 'RESOURCE_NOT_FOUND'})
    return row

def save(db, row, principal, action):
    db.add(row)
    try:
        db.flush()
        record_audit(db, action='QMS_' + action, request_id=uuid.uuid4().hex, target_id=row.id,
            actor_id=principal.subject, actor_role=principal.role, after={'content_sha256': digest(canonical(out(row)))})
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, detail={'code': 'DUPLICATE_OR_CONCURRENT_UPDATE'})
    return out(row)

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class RequirementInput(Strict):
    requirement_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    requirement_type: str = Field(pattern='^(USER|SYSTEM|SOFTWARE|INTERFACE|SECURITY|PRIVACY|AI_MODEL|DATA|USABILITY|REGULATORY|OPERATIONAL)$')
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    source: str = Field(min_length=3, max_length=500)
    rationale: str = Field(min_length=3, max_length=1000)
    safety_classification: str = Field(default='UNASSESSED', pattern='^(UNASSESSED|SAFETY_RELATED|NON_SAFETY)$')
    security_relevance: bool = False
    ai_relevance: bool = False
    owner_role: str = Field(pattern='^(ML_ENGINEER|QA_RA|RADIOLOGIST|TECHNICIAN)$')

class ApprovalInput(Strict):
    version: int = Field(ge=1)
    meaning: str = Field(pattern='^(REVIEWED|APPROVED|RELEASE_AUTHORIZED|EFFECTIVENESS_CONFIRMED|RISK_ACCEPTED|DOCUMENT_EFFECTIVE)$')
    reason: str = Field(min_length=3, max_length=1000)

@router.post('/requirements', status_code=201)
def create_requirement(body: RequirementInput, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    validate_text(canonical(body.model_dump()))
    if p.role == 'ML_ENGINEER' and body.requirement_type not in {'AI_MODEL', 'DATA', 'SOFTWARE', 'SECURITY', 'INTERFACE'}:
        raise HTTPException(403, detail={'code': 'REQUIREMENT_TYPE_NOT_ALLOWED'})
    data = body.model_dump(exclude={'title', 'requirement_id'})
    warnings = ambiguity(body.description)
    data.update(version=1, created_by=p.subject, status='REVIEW_REQUIRED' if warnings else 'DRAFT', warnings=warnings)
    row = legacy.TestRequirement(requirement_id=body.requirement_id, title=body.title, qms_data=data)
    return save(db, row, p, 'REQUIREMENT_CREATED')

@router.get('/requirements')
def requirements(p=Depends(access()), db: Session=Depends(get_db)):
    return [out(r) for r in db.scalars(select(legacy.TestRequirement))]

@router.get('/requirements/{requirement_id}')
def requirement(requirement_id: str, p=Depends(access()), db: Session=Depends(get_db)):
    return out(get(db, legacy.TestRequirement, requirement_id))

@router.patch('/requirements/{requirement_id}')
def update_requirement(requirement_id: str, body: RequirementInput, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    row = get(db, legacy.TestRequirement, requirement_id)
    if p.role == 'ML_ENGINEER' and (body.requirement_type not in {'AI_MODEL','DATA','SOFTWARE','SECURITY','INTERFACE'} or row.qms_data.get('created_by') != p.subject):
        raise HTTPException(403, detail={'code': 'REQUIREMENT_TYPE_NOT_ALLOWED'})
    if row.qms_data.get('status') not in {'DRAFT', 'REVIEW_REQUIRED', 'CHANGES_REQUESTED'}:
        raise HTTPException(409, detail={'code': 'STATE_CONFLICT'})
    if body.requirement_id != row.requirement_id: raise HTTPException(409, detail={'code': 'IDENTIFIER_IMMUTABLE'})
    validate_text(canonical(body.model_dump()))
    data = body.model_dump(exclude={'title', 'requirement_id'})
    data.update(version=row.qms_data.get('version', 0) + 1, created_by=row.qms_data.get('created_by'),
        status='REVIEW_REQUIRED' if ambiguity(body.description) else 'DRAFT', warnings=ambiguity(body.description))
    row.title = body.title; row.qms_data = data
    return save(db, row, p, 'REQUIREMENT_UPDATED')

@router.post('/requirements/{requirement_id}/submit-review')
def submit_requirement(requirement_id: str, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    row = get(db, legacy.TestRequirement, requirement_id)
    if row.qms_data.get('status') not in {'DRAFT', 'REVIEW_REQUIRED', 'CHANGES_REQUESTED'}:
        raise HTTPException(409, detail={'code': 'STATE_CONFLICT'})
    row.qms_data = {**row.qms_data, 'status': 'IN_REVIEW'}
    return save(db, row, p, 'REQUIREMENT_REVIEW_REQUESTED')

def approve_gate(row, p, body, author, version):
    validate_text(body.reason)
    require_electronic_approval(p, author, body.version, version, body.meaning, body.reason)

@router.post('/requirements/{requirement_id}/approve')
def approve_requirement(requirement_id: str, body: ApprovalInput, p=Depends(access({'QA_RA'})), db: Session=Depends(get_db)):
    row = get(db, legacy.TestRequirement, requirement_id)
    if row.qms_data.get('status') != 'IN_REVIEW': raise HTTPException(409, detail={'code': 'STATE_CONFLICT'})
    gaps = requirement_gaps(db, row)
    if gaps: raise HTTPException(409, detail={'code': 'TRACEABILITY_GAPS', 'gaps': gaps})
    approve_gate(row, p, body, row.qms_data.get('created_by'), row.qms_data.get('version', 1))

class RiskInput(Strict):
    risk_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,32}$')
    hazard: str = Field(min_length=3, max_length=120)
    hazardous_situation: str = Field(min_length=3, max_length=1000)
    foreseeable_sequence: str = Field(min_length=3, max_length=1000)
    harm: str = Field(min_length=3, max_length=1000)
    severity: int = Field(ge=1, le=5)
    probability: int = Field(ge=1, le=5)
    risk_controls: list[str] = Field(default_factory=list, max_length=50)
    verification_ids: list[str] = Field(default_factory=list, max_length=50)
    residual_severity: int = Field(ge=1, le=5)
    residual_probability: int = Field(ge=1, le=5)
    owner_role: str = Field(pattern='^(QA_RA|ML_ENGINEER)$')

def risk_level(score):
    from app.core.config import settings
    return 'CRITICAL' if score >= settings.qms_risk_critical_score else 'HIGH' if score >= settings.qms_risk_high_score else 'LOW'

@router.post('/risks', status_code=201)
def create_risk(body: RiskInput, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    validate_text(canonical(body.model_dump()))
    data = body.model_dump(); score = body.residual_severity * body.residual_probability
    data.update(initial_risk=body.severity*body.probability, residual_score=score,
        benefit_risk_required=risk_level(score) in {'HIGH', 'CRITICAL'}, status='DRAFT', version=1, created_by=p.subject)
    return save(db, legacy.AIRisk(id=body.risk_id, name=body.hazard, control='; '.join(body.risk_controls),
        verification_test='', owner=body.owner_role, residual_risk=risk_level(score), qms_data=data), p, 'RISK_CREATED')

@router.get('/risks')
def risks(p=Depends(access()), db: Session=Depends(get_db)): return [out(r) for r in db.scalars(select(legacy.AIRisk))]

@router.get('/risks/{risk_id}')
def risk(risk_id: str, p=Depends(access()), db: Session=Depends(get_db)): return out(get(db, legacy.AIRisk, risk_id))

@router.patch('/risks/{risk_id}')
def edit_risk(risk_id: str, body: RiskInput, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    row = get(db, legacy.AIRisk, risk_id)
    if row.qms_data.get('status') not in {'DRAFT', 'REVIEW_REQUIRED'}: raise HTTPException(409, detail={'code': 'STATE_CONFLICT'})
    if body.risk_id != risk_id: raise HTTPException(409, detail={'code': 'IDENTIFIER_IMMUTABLE'})
    validate_text(canonical(body.model_dump()))
    row.qms_data = {**body.model_dump(), 'version': row.qms_data.get('version', 0)+1,
        'created_by': row.qms_data.get('created_by'), 'status': 'DRAFT'}
    row.name = body.hazard; row.control = '; '.join(body.risk_controls); row.owner = body.owner_role
    row.residual_risk = risk_level(body.residual_severity * body.residual_probability)
    return save(db, row, p, 'RISK_UPDATED')

@router.post('/risks/{risk_id}/evaluate')
def evaluate_risk(risk_id: str, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    row = get(db, legacy.AIRisk, risk_id); data = row.qms_data
    if data.get('status') not in {'DRAFT', 'REVIEW_REQUIRED'}: raise HTTPException(409, detail={'code': 'STATE_CONFLICT'})
    if 'severity' not in data: raise HTTPException(409, detail={'code': 'HUMAN_INPUT_REQUIRED'})
    score = data['residual_severity']*data['residual_probability']; row.residual_risk = risk_level(score)
    row.qms_data = {**data, 'initial_risk': data['severity']*data['probability'], 'residual_score': score,
        'status': 'REVIEW_REQUIRED', 'benefit_risk_required': row.residual_risk in {'HIGH', 'CRITICAL'}}
    return save(db, row, p, 'RISK_EVALUATED')

@router.post('/risks/{risk_id}/approve')
def approve_risk(risk_id: str, body: ApprovalInput, p=Depends(access({'QA_RA'})), db: Session=Depends(get_db)):
    row = get(db, legacy.AIRisk, risk_id)
    if row.qms_data.get('status') != 'REVIEW_REQUIRED': raise HTTPException(409, detail={'code': 'STATE_CONFLICT'})
    if not row.qms_data.get('risk_controls') or not row.qms_data.get('verification_ids'):
        raise HTTPException(409, detail={'code': 'UNRESOLVED_RISK_CONTROLS'})
    approve_gate(row, p, body, row.qms_data.get('created_by'), row.qms_data.get('version', 1))

@router.get('/risk-matrix')
def matrix(p=Depends(access()), db: Session=Depends(get_db)):
    return {'method': 'Severity × Probability; configurable research matrix, not certified',
        'cells': [{'severity': s, 'probability': v, 'score': s*v, 'level': risk_level(s*v)} for s in range(1,6) for v in range(1,6)],
        'risks': risks(p, db), 'acceptance': 'QA_RA_REVIEW_REQUIRED'}

TARGETS = {'REQUIREMENT': legacy.TestRequirement, 'RISK': legacy.AIRisk, 'TEST_SCENARIO': legacy.TestScenario,
    'TEST_EXECUTION': legacy.TestExecution, 'EVIDENCE': legacy.TestEvidence, 'DEFECT': legacy.DefectRecord,
    'CAPA': legacy.OperationalCapa, 'DOCUMENT': ControlledDocument, 'CHANGE': ChangeRequest,
    'IMPACT': ImpactAssessment, 'MODEL': legacy.ModelRelease, 'APPROVAL': ElectronicApproval,
    'AUDIT_EVENT': legacy.AuditEvent, 'EXTERNAL_TRANSFER': legacy.ExternalTransferJob}
TARGETS.update({'DATASET': legacy.DatasetVersion, 'MODEL_VALIDATION': legacy.ModelValidationRun,
    'DEPLOYMENT': legacy.DeploymentRecord, 'MONITORING': legacy.MonitoringSnapshot,
    'MODEL_APPROVAL': legacy.ModelApproval, 'LEGACY_CAPA': legacy.Capa})

def item_version(row): return getattr(row, 'current_version', (getattr(row, 'qms_data', {}) or {}).get('version', 1))
def resolve(db, kind, key):
    if kind in TARGETS: return db.get(TARGETS[kind], key)
    if kind == 'IMPLEMENTATION_FILE':
        root = Path(__file__).resolve().parents[3]
        path = (root / key).resolve()
        if not path.is_relative_to(root) or key.startswith(('/', '\\')) or path.suffix not in {'.py','.ts','.tsx','.css'}:
            return None
        if not path.is_file() or path.stat().st_size > 5 * 1024 * 1024: return None
        return SimpleNamespace(current_version=1, fingerprint=digest(path.read_bytes()))
    if kind == 'API':
        from app.main import app
        if not any(key == method + ' ' + r.path for r in app.routes for method in (getattr(r,'methods',None) or [])): return None
        return SimpleNamespace(current_version=1, fingerprint=digest(key))
    if kind == 'DB_MODEL':
        from app.db.database import Base
        if key not in Base.metadata.tables: return None
        table = Base.metadata.tables[key]
        return SimpleNamespace(current_version=1, fingerprint=digest(canonical([(c.name,str(c.type),c.nullable) for c in table.columns])))
    if kind == 'RISK_CONTROL':
        try:
            risk_id, index = key.rsplit('#',1); row = db.get(legacy.AIRisk,risk_id)
            if row is None or int(index)<0: return None
            control = row.qms_data['risk_controls'][int(index)]
            return SimpleNamespace(current_version=item_version(row), fingerprint=digest(control))
        except (ValueError,KeyError,IndexError): return None
    return None
def link_status(db, row):
    source = resolve(db, row.source_type, row.source_id); target = resolve(db, row.target_type, row.target_id)
    if source is None or target is None: return 'ORPHAN'
    if item_version(target) != row.version or item_version(source) != row.evidence.get('source_version'):
        return 'VERSION_MISMATCH'
    for side,item in [('source',source),('target',target)]:
        if hasattr(item,'fingerprint') and row.evidence.get(side+'_hash') != item.fingerprint:
            return 'CONTENT_MISMATCH'
    return 'VALID'

class LinkInput(Strict):
    source_type: str
    source_id: str = Field(min_length=1, max_length=100)
    relationship: str = Field(pattern=r'^[A-Z_]{3,64}$')
    target_type: str
    target_id: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    source_version: int = Field(ge=1)

@router.post('/traceability-links', status_code=201)
def create_link(body: LinkInput, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    row = TraceabilityLink(**body.model_dump(exclude={'source_version'}), evidence={'source_version': body.source_version}, created_by=p.subject)
    for side,kind,key in [('source',body.source_type,body.source_id),('target',body.target_type,body.target_id)]:
        item=resolve(db,kind,key)
        if item is not None and hasattr(item,'fingerprint'): row.evidence[side+'_hash']=item.fingerprint
    state = link_status(db, row)
    if state != 'VALID': raise HTTPException(409, detail={'code': state})
    return save(db, row, p, 'TRACE_LINK_CREATED')

def links(db): return [{**out(r), 'integrity_status': link_status(db, r)} for r in db.scalars(select(TraceabilityLink))]
def requirement_gaps(db, row):
    attached = [r for r in links(db) if r['integrity_status']=='VALID' and
        ((r['source_type']=='REQUIREMENT' and r['source_id']==row.id) or (r['target_type']=='REQUIREMENT' and r['target_id']==row.id))]
    types = {r['source_type'] for r in attached} | {r['target_type'] for r in attached}
    natural_test = db.scalar(select(legacy.TestScenario).where(legacy.TestScenario.requirement_id == row.requirement_id))
    gaps = [] if 'TEST_SCENARIO' in types or natural_test else ['MISSING_TEST_SCENARIO']
    if row.qms_data.get('safety_classification') == 'SAFETY_RELATED' and 'RISK' not in types: gaps.append('MISSING_RISK_LINK')
    return gaps

@router.get('/traceability')
def traceability(p=Depends(access()), db: Session=Depends(get_db)): return links(db)

@router.get('/traceability-export')
def traceability_export(p=Depends(access()), db: Session=Depends(get_db)):
    import csv
    from io import StringIO
    output=StringIO(newline='')
    fields=['source_type','source_id','relationship','target_type','target_id','version','integrity_status']
    writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader()
    for row in links(db):
        values={key:str(row[key]) for key in fields}
        writer.writerow({key:("'"+value if value.startswith(('=','+','-','@','\t','\r')) else value) for key,value in values.items()})
    return Response('\ufeff'+output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=qms-traceability.csv'})

@router.get('/traceability/gaps')
def gaps(p=Depends(access()), db: Session=Depends(get_db)):
    return [{'id': r.id, 'requirement_id': r.requirement_id, 'gaps': g} for r in db.scalars(select(legacy.TestRequirement)) if (g := requirement_gaps(db, r))]

@router.get('/traceability/orphans')
def orphans(p=Depends(access()), db: Session=Depends(get_db)): return [r for r in links(db) if r['integrity_status']!='VALID']

@router.get('/traceability/{item_type}/{item_id}')
def item_links(item_type: str, item_id: str, p=Depends(access()), db: Session=Depends(get_db)):
    if resolve(db, item_type, item_id) is None: raise HTTPException(404, detail={'code': 'RESOURCE_NOT_FOUND'})
    return [r for r in links(db) if (r['source_type']==item_type and r['source_id']==item_id) or (r['target_type']==item_type and r['target_id']==item_id)]

@router.get('/requirements/{requirement_id}/traceability')
def requirement_trace(requirement_id: str, p=Depends(access()), db: Session=Depends(get_db)):
    return item_links('REQUIREMENT', requirement_id, p, db)

class DocumentInput(Strict):
    use_sllm: bool = False
    document_number: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    document_type: str = Field(pattern=r'^[A-Z_]{3,64}$')
    title: str = Field(min_length=3, max_length=200)
    requirement_ids: list[str] = Field(default_factory=list, max_length=100)

class NewVersion(Strict):
    expected_version: int = Field(ge=1)
    content: str = Field(min_length=10, max_length=100000)
    change_summary: str = Field(min_length=3, max_length=1000)

def latest(db, row):
    version = db.scalar(select(ControlledDocumentVersion).where(ControlledDocumentVersion.document_id==row.id,
        ControlledDocumentVersion.version==row.current_version))
    if version is None: raise HTTPException(409, detail={'code': 'VERSION_MISSING'})
    return version

def check_document(db, row):
    version = latest(db, row)
    if digest(version.content) != version.content_sha256:
        db.add(legacy.SecurityEvent(event_type='QMS_DOCUMENT_INTEGRITY_FAILED', request_id=uuid.uuid4().hex,
            details={'document_id': row.id})); db.commit()
        raise HTTPException(409, detail={'code': 'INTEGRITY_FAILED', 'high_risk_block': True})
    validate_text(version.content)
    return version

@router.post('/documents/generate', status_code=201)
def generate(body: DocumentInput, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    validate_text(canonical(body.model_dump()))
    sources = []
    for key in body.requirement_ids:
        r = get(db, legacy.TestRequirement, key)
        sources.append({'requirement_id': r.requirement_id, 'version': item_version(r), 'title': r.title})
    content = generate_draft(body.document_type, body.title, sources)
    if body.use_sllm:
        from app.core.config import settings
        from app.services.qms_agent import generate_qms_draft
        institution=settings.integration_principal_institutions.get(p.subject)
        if not institution: raise HTTPException(403,detail={'code':'INSTITUTION_MAPPING_REQUIRED'})
        generated=generate_qms_draft(body.document_type,body.title,p.role,institution)
        content=generated['content'];sources+=generated['source_references']
        sources.append({'generation_mode':generated['mode'],'trace':generated['trace'],'validation':'MANUAL_REVIEW_REQUIRED'})
    # Independent rule validation runs after the generation graph finishes.
    validate_text(content)
    row = ControlledDocument(document_number=body.document_number, document_type=body.document_type,
        title=body.title, owner_role=p.role, created_by=p.subject)
    db.add(row)
    try: db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, detail={'code': 'DUPLICATE_DOCUMENT_NUMBER'})
    db.add(ControlledDocumentVersion(document_id=row.id, version=1, content=content, content_sha256=digest(content),
        change_summary='Initial draft', source_references=sources, created_by=p.subject))
    return save(db, row, p, 'DOCUMENT_GENERATED')

@router.get('/documents')
def documents(p=Depends(access()), db: Session=Depends(get_db)): return [out(r) for r in db.scalars(select(ControlledDocument))]

@router.get('/documents/{document_id}')
def document(document_id: str, p=Depends(access()), db: Session=Depends(get_db)):
    row = get(db, ControlledDocument, document_id)
    return {**out(row), 'current': out(check_document(db, row))}

@router.get('/documents/{document_id}/versions')
def versions(document_id: str, p=Depends(access()), db: Session=Depends(get_db)):
    get(db, ControlledDocument, document_id)
    return [out(r) for r in db.scalars(select(ControlledDocumentVersion).where(ControlledDocumentVersion.document_id==document_id).order_by(ControlledDocumentVersion.version))]

@router.post('/documents/{document_id}/new-version')
def new_version(document_id: str, body: NewVersion, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    row = get(db, ControlledDocument, document_id); check_document(db, row)
    if row.current_version != body.expected_version: raise HTTPException(409, detail={'code': 'VERSION_CONFLICT'})
    if row.status in {'RETIRED', 'SUPERSEDED', 'REJECTED'}: raise HTTPException(409, detail={'code': 'STATE_CONFLICT'})
    validate_text(body.content); validate_text(body.change_summary)
    row.current_version += 1; row.status = 'DRAFT'; row.effective_date = None
    db.add(ControlledDocumentVersion(document_id=row.id, version=row.current_version,
        content=body.content, content_sha256=digest(body.content), change_summary=body.change_summary, created_by=p.subject))
    return save(db, row, p, 'DOCUMENT_VERSION_CREATED')

@router.post('/documents/{document_id}/submit-review')
def submit_document(document_id: str, p=Depends(access(WRITE)), db: Session=Depends(get_db)):
    row = get(db, ControlledDocument, document_id); check_document(db, row)
    if row.status not in {'DRAFT', 'CHANGES_REQUESTED'}: raise HTTPException(409, detail={'code': 'STATE_CONFLICT'})
    row.status = 'IN_REVIEW'
    return save(db, row, p, 'DOCUMENT_REVIEW_REQUESTED')

class ReviewInput(Strict):
    version: int = Field(ge=1)
    decision: str = Field(pattern='^(CHANGES_REQUESTED|APPROVAL_REQUIRED|REJECTED)$')
    comment: str = Field(min_length=3, max_length=2000)

@router.post('/documents/{document_id}/reviews')
def review_document(document_id: str, body: ReviewInput, p=Depends(access({'QA_RA'})), db: Session=Depends(get_db)):
    row = get(db, ControlledDocument, document_id); v = check_document(db, row)
    if row.status != 'IN_REVIEW' or body.version != row.current_version: raise HTTPException(409, detail={'code': 'STATE_OR_VERSION_CONFLICT'})
    if p.subject in {row.created_by, v.created_by}: raise HTTPException(409, detail={'code': 'SEPARATION_OF_DUTIES_REQUIRED'})
    validate_text(body.comment)
    db.add(DocumentReview(document_version_id=v.id, reviewer_id=p.subject, reviewer_role=p.role, decision=body.decision, comment=body.comment))
    row.status = body.decision
    return save(db, row, p, 'DOCUMENT_REVIEWED')

@router.post('/documents/{document_id}/approve')
def approve_document(document_id: str, body: ApprovalInput, p=Depends(access({'QA_RA'})), db: Session=Depends(get_db)):
    row = get(db, ControlledDocument, document_id); v = check_document(db, row)
    if row.status != 'APPROVAL_REQUIRED': raise HTTPException(409, detail={'code': 'STATE_CONFLICT'})
    if p.subject == row.created_by: raise HTTPException(409, detail={'code': 'SEPARATION_OF_DUTIES_REQUIRED'})
    approve_gate(row, p, body, v.created_by, row.current_version)

@router.post('/documents/{document_id}/make-effective')
def effective_document(document_id: str, body: ApprovalInput, p=Depends(access({'QA_RA'})), db: Session=Depends(get_db)):
    row = get(db, ControlledDocument, document_id); v = check_document(db, row)
    if row.status != 'APPROVED': raise HTTPException(409, detail={'code': 'STATE_CONFLICT'})
    approve_gate(row, p, body, v.created_by, row.current_version)

@router.get('/documents/{document_id}/download')
def download_document(document_id: str, p=Depends(access()), db: Session=Depends(get_db)):
    row = get(db, ControlledDocument, document_id); v = check_document(db, row)
    from .validation import guard_critical
    guard_critical(db)
    if row.status in {'APPROVED', 'EFFECTIVE'}:
        approvals = db.scalars(select(ElectronicApproval).where(ElectronicApproval.target_id==row.id,
            ElectronicApproval.target_version==row.current_version)).all()
        if not approvals or any(a.content_sha256 != v.content_sha256 for a in approvals):
            raise HTTPException(409, detail={'code': 'APPROVAL_INTEGRITY_FAILED'})
    return Response(v.content, media_type='text/markdown', headers={'Content-Disposition': f'attachment; filename=qms-{row.id}-v{row.current_version}.md'})

@router.get('/approvals')
def approvals(p=Depends(access({'QA_RA', 'ADMIN'})), db: Session=Depends(get_db)):
    return {'status': 'REAUTHENTICATION_NOT_CONFIGURED', 'records': [out(r) for r in db.scalars(select(ElectronicApproval))], 'legal_compliance': 'NOT_VERIFIED'}

@router.get('/audit-chain/status')
@router.post('/audit-chain/verify')
def chain_status(p=Depends(access({'QA_RA', 'ADMIN'})), db: Session=Depends(get_db)):
    result = verify_chain(db)
    if result['status']=='INTEGRITY_FAILED':
        db.add(legacy.SecurityEvent(event_type='QMS_AUDIT_INTEGRITY_FAILED', request_id=uuid.uuid4().hex, details={'errors': result['errors']})); db.commit()
    return result

@router.get('/audit-chain/events')
def chain_events(p=Depends(access({'QA_RA', 'ADMIN'})), db: Session=Depends(get_db)):
    return [out(r) for r in db.scalars(select(AuditChainEntry).order_by(AuditChainEntry.sequence))]

@router.get('/dashboard')
def dashboard(p=Depends(access()), db: Session=Depends(get_db)):
    reqs = list(db.scalars(select(legacy.TestRequirement))); gap_rows = gaps(p, db)
    tests = list(db.scalars(select(legacy.TestExecution)))
    return {'requirements': len(reqs), 'unlinked_requirements': len(gap_rows),
        'test_results': {s: sum(t.status==s for t in tests) for s in ('PASS','FAIL','BLOCKED')},
        'open_defects': len(list(db.scalars(select(legacy.DefectRecord).where(legacy.DefectRecord.status!='CLOSED')))),
        'open_capas': len(list(db.scalars(select(legacy.OperationalCapa).where(legacy.OperationalCapa.status!='CLOSED')))),
        'pending_documents': len(list(db.scalars(select(ControlledDocument).where(ControlledDocument.status.in_(['IN_REVIEW','APPROVAL_REQUIRED']))))),
        'critical_risks': len(list(db.scalars(select(legacy.AIRisk).where(legacy.AIRisk.residual_risk=='CRITICAL')))),
        'traceability_completeness': (len(reqs)-len(gap_rows))/len(reqs) if reqs else None,
        'audit_chain': verify_chain(db)['status'], 'release_block': True,
        'reason': 'REAUTHENTICATION_NOT_CONFIGURED', 'clinical_performance': 'NOT_MEASURED', 'mode': 'PARTIAL'}
