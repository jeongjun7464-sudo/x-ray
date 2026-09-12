import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app, limiter
from app.db.database import Base, get_db
from app.db.models import AuditEvent, TestRequirement as Requirement
from app.db.qms_models import ControlledDocumentVersion, TraceabilityLink
from app.core.config import settings
from app.core.auth import issue_session_token

@pytest.fixture
def env(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine); factory=sessionmaker(bind=engine,autoflush=False)
    def session():
        with factory() as db: yield db
    app.dependency_overrides[get_db]=session
    monkeypatch.setattr(settings,'auth_session_secret','phase30-synthetic-test-secret-at-least-32')
    limiter._events.clear()
    client=TestClient(app)
    def headers(role='QA_RA',subject='qa-reviewer'):
        token,_=issue_session_token(subject,role,settings.auth_session_secret)
        return {'Authorization':'Bearer '+token}
    yield client,headers,factory
    app.dependency_overrides.pop(get_db,None);engine.dispose()

def req(): return {'requirement_id':'REQ-1','requirement_type':'SOFTWARE','title':'저장 검증 요구사항',
    'description':'분석 응답시간을 ms 단위 정수로 저장한다.','source':'SYNTHETIC_SPEC','rationale':'재현 가능한 시험',
    'owner_role':'QA_RA','safety_classification':'SAFETY_RELATED'}

def test_requirements_rbac_duplicates_gaps_and_ambiguity(env):
    c,h,_=env
    assert c.get('/api/v1/qms/requirements').status_code==401
    assert c.post('/api/v1/qms/requirements',headers=h('TECHNICIAN'),json=req()).status_code==403
    r=c.post('/api/v1/qms/requirements',headers=h(),json=req());assert r.status_code==201,r.text
    key=r.json()['id'];assert c.post('/api/v1/qms/requirements',headers=h(),json=req()).status_code==409
    gaps=c.get('/api/v1/qms/traceability/gaps',headers=h()).json()
    assert set(gaps[0]['gaps'])=={'MISSING_TEST_SCENARIO','MISSING_RISK_LINK'}
    body=req();body['description']='가능하면 빠르게 처리해야 한다.'
    r=c.patch('/api/v1/qms/requirements/'+key,headers=h(),json=body)
    assert r.json()['status']=='REVIEW_REQUIRED' and r.json()['version']==2
    assert c.post('/api/v1/qms/requirements/'+key+'/submit-review',headers=h()).status_code==200
    assert c.post('/api/v1/qms/requirements/'+key+'/submit-review',headers=h()).status_code==409

def test_document_versions_review_reauthentication_and_tampering(env):
    c,h,dbf=env
    p='/api/v1/qms/documents'
    r=c.post(p+'/generate',headers=h('ML_ENGINEER','doc-author'),json={'document_number':'DOC-1','document_type':'TEST_REPORT','title':'합성 시험 초안'})
    assert r.status_code==201,r.text
    key=r.json()['id'];base=p+'/'+key
    assert c.get(base,headers=h()).json()['current']['content_sha256']
    assert c.post(base+'/submit-review',headers=h()).status_code==200
    assert c.post(base+'/reviews',headers=h('QA_RA','doc-author'),json={'version':1,'decision':'APPROVAL_REQUIRED','comment':'Synthetic review'}).status_code==409
    assert c.post(base+'/reviews',headers=h(),json={'version':1,'decision':'APPROVAL_REQUIRED','comment':'Synthetic review'}).status_code==200
    approval=c.post(base+'/approve',headers=h(),json={'version':1,'meaning':'APPROVED','reason':'Independent review'})
    assert approval.json()['detail']['code']=='REAUTHENTICATION_NOT_CONFIGURED'
    with dbf() as db:
        db.execute(text("UPDATE controlled_document_versions SET content='tampered' WHERE document_id=:id"),{'id':key});db.commit()
    assert c.get(base+'/download',headers=h()).json()['detail']['code']=='INTEGRITY_FAILED'

def test_audit_chain_detects_mutation_and_missing_event(env):
    c,h,factory=env
    assert c.post('/api/v1/qms/requirements',headers=h(),json=req()).status_code==201
    assert c.get('/api/v1/qms/audit-chain/status',headers=h()).json()['status']=='VERIFIED'
    with factory() as db:
        db.execute(text("UPDATE audit_events SET action='FORGED'"));db.commit()
    result=c.post('/api/v1/qms/audit-chain/verify',headers=h()).json()
    assert result['status']=='INTEGRITY_FAILED'
    assert c.post('/api/v1/qms/audit-packages',headers=h()).status_code==409

def test_change_impact_requires_full_regression_and_no_automatic_release(env):
    c,h,_=env
    r=c.post('/api/v1/qms/change-requests',headers=h(),json={'change_id':'CHG-1','title':'합성 변경','description':'Synthetic change only','reason':'Test validation'})
    assert r.status_code==201
    path='/api/v1/qms/change-requests/'+r.json()['id']
    body={'assessment_type':'SOFTWARE','impact_level':'HIGH','affected_items':[], 'regression_scope':['test'],
        'regulatory_impact':'Review required','cybersecurity_impact':'Review required','privacy_impact':'No patient data','interoperability_impact':'No live connection'}
    assert c.post(path+'/impact-assessment',headers=h(),json=body).status_code==422
    body['regression_scope']=['FULL_REGRESSION']
    assert c.post(path+'/impact-assessment',headers=h(),json=body).status_code==200
    assert c.post(path+'/release',headers=h('ADMIN'),json={'version':1,'meaning':'RELEASE_AUTHORIZED','reason':'Synthetic review'}).status_code==409

def test_capa_not_closed_by_legacy_route(env):
    c,h,_=env
    r=c.post('/api/v1/qms/capas',headers=h(),json={'error_type':'TEST_FAILURE','severity':'HIGH','owner':'qa-owner'})
    assert r.status_code==201
    key=r.json()['id']
    assert c.patch('/api/v1/capa/'+key,headers=h(),json={'status':'CLOSED','approved_by':'forged'}).status_code==409
    assert c.post('/api/v1/qms/capas/'+key+'/close',headers=h(),json={'version':1,'meaning':'EFFECTIVENESS_CONFIRMED','reason':'Synthetic review'}).status_code==409

def test_draft_package_integrity_and_legacy_access_block(env):
    c,h,_=env
    r=c.post('/api/v1/qms/audit-packages',headers=h());assert r.status_code==201,r.text
    key=r.json()['id']; assert r.json()['status']=='INCOMPLETE_DRAFT'
    download=c.get('/api/v1/qms/audit-packages/'+key+'/download',headers=h())
    assert download.status_code==200 and download.content[:2]==b'PK'
    assert c.get('/api/v1/audit-packages/'+key+'/download').status_code==403
    assert c.get('/api/v1/qms/audit-packages/'+key+'/download').status_code==401

def test_qms_rules_missing_evidence_not_pass(env):
    c,h,_=env
    r=c.post('/api/v1/qms/consistency/validate',headers=h())
    assert r.status_code==200,r.text
    assert len(r.json()['findings'])==20
    assert r.json()['summary']['NOT_VERIFIABLE']==20

def test_traceability_both_directions_versions_and_orphans(env):
    c,h,factory=env
    r=c.post('/api/v1/qms/requirements',headers=h(),json=req()); key=r.json()['id']
    body={'source_type':'REQUIREMENT','source_id':key,'relationship':'STORED_IN','target_type':'DB_MODEL','target_id':'test_requirements','version':1,'source_version':1}
    link=c.post('/api/v1/qms/traceability-links',headers=h(),json=body)
    assert link.status_code==201,link.text
    assert len(c.get('/api/v1/qms/traceability/DB_MODEL/test_requirements',headers=h()).json())==1
    assert len(c.get('/api/v1/qms/requirements/'+key+'/traceability',headers=h()).json())==1
    assert c.post('/api/v1/qms/traceability-links',headers=h(),json=body).status_code==409
    edited=req();edited['description']='분석 응답시간을 정수 ms 단위로 저장하고 조회한다.'
    assert c.patch('/api/v1/qms/requirements/'+key,headers=h(),json=edited).status_code==200
    assert c.get('/api/v1/qms/traceability/orphans',headers=h()).json()[0]['integrity_status']=='VERSION_MISMATCH'
    with factory() as db:
        db.execute(text('DELETE FROM test_requirements WHERE id=:id'),{'id':key});db.commit()
    assert c.get('/api/v1/qms/traceability/orphans',headers=h()).json()[0]['integrity_status']=='ORPHAN'
    export=c.get('/api/v1/qms/traceability-export',headers=h())
    assert export.status_code==200 and 'ORPHAN' in export.text

def test_risk_evaluation_critical_control_block(env):
    c,h,_=env
    body={'risk_id':'RISK-1','hazard':'합성 보안 위험','hazardous_situation':'Synthetic situation','foreseeable_sequence':'Synthetic sequence','harm':'Synthetic harm',
        'severity':5,'probability':5,'residual_severity':5,'residual_probability':5,'owner_role':'QA_RA'}
    r=c.post('/api/v1/qms/risks',headers=h(),json=body);assert r.status_code==201,r.text
    assert r.json()['residual_score']==25 and r.json()['residual_risk']=='CRITICAL'
    assert c.post('/api/v1/qms/risks/RISK-1/evaluate',headers=h()).status_code==200
    r=c.post('/api/v1/qms/risks/RISK-1/approve',headers=h(),json={'version':1,'meaning':'RISK_ACCEPTED','reason':'Synthetic test'})
    assert r.json()['detail']['code']=='UNRESOLVED_RISK_CONTROLS'
    result=c.post('/api/v1/qms/consistency/validate',headers=h()).json()
    assert result['high_risk_block'] and any(f['rule_id']=='QMS-017' and f['status']=='FAIL' for f in result['findings'])

def test_document_new_version_and_append_only_storage(env):
    c,h,factory=env
    row=c.post('/api/v1/qms/documents/generate',headers=h(),json={'document_number':'DOC-2','document_type':'TEST_REPORT','title':'합성 시험 문서'}).json()
    path='/api/v1/qms/documents/'+row['id']
    body={'expected_version':1,'content':'DRAFT — Synthetic evidence only. NOT_MEASURED.','change_summary':'Added synthetic scope'}
    assert c.post(path+'/new-version',headers=h(),json=body).json()['current_version']==2
    assert c.post(path+'/new-version',headers=h(),json=body).status_code==409
    assert len(c.get(path+'/versions',headers=h()).json())==2
    with factory() as db:
        version=db.scalar(select(ControlledDocumentVersion));version.content='overwrite'
        with pytest.raises(ValueError,match='APPEND_ONLY_RECORD'):db.commit()

def test_chain_gap_and_package_payload_tampering(env):
    c,h,factory=env
    package=c.post('/api/v1/qms/audit-packages',headers=h()).json()
    with factory() as db:
        db.execute(text("UPDATE audit_packages SET payload_base64='invalid' WHERE id=:id"),{'id':package['id']});db.commit()
    assert c.get('/api/v1/qms/audit-packages/'+package['id']+'/download',headers=h()).status_code==409
    with factory() as db:
        db.execute(text('DELETE FROM audit_events'));db.commit()
    assert c.get('/api/v1/qms/audit-chain/status',headers=h()).json()['status']=='INTEGRITY_FAILED'

def test_explicit_transitions_do_not_allow_approval_shortcuts(env):
    c,h,_=env
    change=c.post('/api/v1/qms/change-requests',headers=h(),json={'change_id':'CHG-TRANSITION','title':'합성 전이 시험','description':'Synthetic change request','reason':'Test state transitions'}).json()
    path='/api/v1/qms/change-requests/'+change['id']+'/transition'
    body={'expected_status':'PROPOSED','target_status':'APPROVED','reason':'Synthetic transition'}
    assert c.post(path,headers=h(),json=body).status_code==409
    body['target_status']='IMPACT_ANALYSIS'
    assert c.post(path,headers=h(),json=body).json()['status']=='IMPACT_ANALYSIS'
    assert c.post(path,headers=h(),json=body).status_code==409
    capa=c.post('/api/v1/qms/capas',headers=h(),json={'error_type':'TEST_FAILURE','severity':'LOW','owner':'qa-owner'}).json()
    path='/api/v1/qms/capas/'+capa['id']+'/transition'
    assert c.post(path,headers=h(),json={'expected_status':'CANDIDATE','target_status':'CLOSED','reason':'Synthetic transition'}).status_code==409
    assert c.post(path,headers=h(),json={'expected_status':'CANDIDATE','target_status':'INVESTIGATION','reason':'Synthetic transition'}).status_code==200
