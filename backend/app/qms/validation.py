import uuid
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models as legacy
from app.db.qms_models import ControlledDocument, ControlledDocumentVersion, ElectronicApproval, ChangeRequest, ImpactAssessment
from app.services.qms_integrity import digest
from app.services.qms_validation import validate_text
from .router import router,access,links,requirement_gaps,item_version

def evidence_context(db):
    evidence={f'QMS-{n:03}':None for n in range(1,21)}
    requirements=list(db.scalars(select(legacy.TestRequirement)))
    approved=[r for r in requirements if r.qms_data.get('status')=='APPROVED']
    safety=[r for r in requirements if r.qms_data.get('safety_classification')=='SAFETY_RELATED']
    if approved: evidence['QMS-001']=all('MISSING_TEST_SCENARIO' not in requirement_gaps(db,r) for r in approved)
    if safety: evidence['QMS-002']=all('MISSING_RISK_LINK' not in requirement_gaps(db,r) for r in safety)
    risks=[r for r in db.scalars(select(legacy.AIRisk)) if r.qms_data]
    if risks:
        evidence['QMS-003']=all(r.qms_data.get('verification_ids') and all(db.get(legacy.TestScenario,k) for k in r.qms_data['verification_ids']) for r in risks)
    critical=[r for r in risks if r.residual_risk=='CRITICAL']
    if critical:
        from .workflows import passing_tests
        evidence['QMS-017']=all(bool(r.qms_data.get('risk_controls')) and passing_tests(db,r.qms_data.get('verification_ids',[])) for r in critical)
    failures=list(db.scalars(select(legacy.TestExecution).where(legacy.TestExecution.status=='FAIL')))
    if failures: evidence['QMS-004']=all(db.scalar(select(legacy.DefectRecord).where(legacy.DefectRecord.execution_id==r.id)) is not None for r in failures)
    severe_defects=[r for r in db.scalars(select(legacy.DefectRecord)) if r.qms_data.get('severity') in {'HIGH','CRITICAL'}]
    if severe_defects:
        capas=list(db.scalars(select(legacy.OperationalCapa)))
        evidence['QMS-005']=all(any(r.id in c.qms_data.get('defect_ids',[]) for c in capas) for r in severe_defects)
    changes=list(db.scalars(select(ChangeRequest)))
    if changes:
        evidence['QMS-006']=all(db.scalar(select(ImpactAssessment).where(ImpactAssessment.change_request_id==r.id)) is not None for r in changes)
        evidence['QMS-007']=all(bool(r.affected_tests) and all(db.get(legacy.TestScenario,k) is not None for k in r.affected_tests) for r in changes)
    model_changes=[r for r in changes if r.affected_models]
    if model_changes: evidence['QMS-014']=all(bool(r.affected_risks) and all(db.get(legacy.AIRisk,k) is not None for k in r.affected_risks) for r in model_changes)
    dataset_changes=[r for r in changes if r.affected_datasets]
    if dataset_changes:
        checks=[]
        for change in dataset_changes:
            for key in change.affected_datasets:
                dataset=db.get(legacy.DatasetVersion,key)
                runs=list(db.scalars(select(legacy.ModelValidationRun).where(legacy.ModelValidationRun.validation_type=='FAIRNESS',legacy.ModelValidationRun.dataset_version==dataset.version))) if dataset else []
                checks.append(any(list(db.scalars(select(legacy.ModelValidationMetric).where(legacy.ModelValidationMetric.validation_run_id==run.id,legacy.ModelValidationMetric.value.is_not(None),legacy.ModelValidationMetric.sample_size>0))) for run in runs))
        evidence['QMS-015']=all(checks)
    integration_changes=[r for r in changes if r.affected_integrations]
    if integration_changes:
        evidence['QMS-016']=all(any((scenario:=db.get(legacy.TestScenario,k)) is not None and scenario.input_data.get('integration_test') is True for k in r.affected_tests) for r in integration_changes)
    # Fairness measurements and full integration evidence are deliberately not inferred from IDs.
    versions=list(db.scalars(select(ControlledDocumentVersion)))
    if versions:
        evidence['QMS-009']=all(digest(v.content)==v.content_sha256 for v in versions)
        try:
            for v in versions: validate_text(v.content)
            evidence['QMS-020']=True  # Only the documented text heuristic, not clinical validation.
        except HTTPException: evidence['QMS-020']=False
    metrics=list(db.scalars(select(legacy.ModelValidationMetric)))
    if metrics:
        valid=all(not (m.passed is True and (m.value is None or m.sample_size<=0 or m.status=='NOT_MEASURED')) for m in metrics)
        evidence['QMS-020']=valid if evidence['QMS-020'] is None else evidence['QMS-020'] and valid
    replacements=list(db.scalars(select(ControlledDocument).where(ControlledDocument.supersedes_document_id.is_not(None),ControlledDocument.status=='EFFECTIVE')))
    if replacements:
        evidence['QMS-013']=all((previous:=db.get(ControlledDocument,r.supersedes_document_id)) is not None and previous.status!='EFFECTIVE' for r in replacements)
    approvals=list(db.scalars(select(ElectronicApproval)))
    if approvals:
        evidence['QMS-011']=all(bool(a.reason.strip() and a.meaning) for a in approvals)
        evidence['QMS-012']=all(a.reauthentication_status=='VERIFIED' for a in approvals)
        document_approvals=[a for a in approvals if a.target_type=='DOCUMENT']
        if document_approvals:
            matched=[]; independent=[]
            for a in document_approvals:
                d=db.get(ControlledDocument,a.target_id)
                v=db.scalar(select(ControlledDocumentVersion).where(ControlledDocumentVersion.document_id==a.target_id,ControlledDocumentVersion.version==a.target_version))
                matched.append(bool(d and v and d.current_version==a.target_version and a.content_sha256==v.content_sha256))
                independent.append(bool(d and v and a.signer_id not in {d.created_by,v.created_by}))
            evidence['QMS-008']=all(matched); evidence['QMS-010']=all(independent)
    traces=links(db)
    if traces: evidence['QMS-019']=all(r['integrity_status']=='VALID' for r in traces)
    audit_packages=[r for r in db.scalars(select(legacy.AuditPackage)) if r.manifest.get('qms')]
    if audit_packages:
        from .packages import verify_package
        try:
            for row in audit_packages: verify_package(row)
            evidence['QMS-018']=True
        except HTTPException: evidence['QMS-018']=False
    return {'qms':evidence}

def guard_critical(db):
    from app.services.consistency.engine import ConsistencyEngine
    findings=ConsistencyEngine().validate(evidence_context(db),['QMS'])['findings']
    failures=[f['rule_id'] for f in findings if f['severity']=='CRITICAL' and f['status']=='FAIL']
    if failures:
        db.add(legacy.SecurityEvent(event_type='QMS_CRITICAL_ACTION_BLOCKED',request_id=uuid.uuid4().hex,details={'rules':failures}))
        db.commit()
        raise HTTPException(409,detail={'code':'QMS_INTEGRITY_BLOCK','rules':failures,'high_risk_block':True})

@router.post('/consistency/validate')
def validate_qms(p=Depends(access({'QA_RA'})),db: Session=Depends(get_db)):
    from app.main import _save_consistency
    result=_save_consistency(db,'QMS','QMS','system',evidence_context(db),['QMS'])
    if result.get('high_risk_block'):
        db.add(legacy.SecurityEvent(event_type='QMS_CRITICAL_VALIDATION_FAILED',request_id=uuid.uuid4().hex,
            details={'actions':['RELEASE_BLOCK','DOCUMENT_DOWNLOAD_BLOCK','APPROVAL_BLOCK','QA_RA_REVIEW']}))
    db.commit()
    return result
