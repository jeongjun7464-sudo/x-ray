import base64
from io import BytesIO
import json
import uuid
import zipfile
from datetime import datetime,timezone
from fastapi import Depends,HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models as legacy
from app.db.qms_models import ChangeRequest,ElectronicApproval,ControlledDocumentVersion,AuditEvidence
from app.services.qms_integrity import canonical,digest,verify_chain
from app.services.qms_validation import validate_text
from app.services.consistency.engine import ConsistencyEngine
from .router import router,access,out,get,save,links
from .validation import evidence_context

def package_bytes(db,p,validation_run_id=None):
    chain=verify_chain(db)
    if chain['status']=='INTEGRITY_FAILED': raise HTTPException(409,detail={'code':'AUDIT_INTEGRITY_FAILED'})
    for version in db.scalars(select(ControlledDocumentVersion)):
        if digest(version.content)!=version.content_sha256: raise HTTPException(409,detail={'code':'DOCUMENT_INTEGRITY_FAILED'})
        validate_text(version.content)
    validation=ConsistencyEngine().validate(evidence_context(db),['QMS'])
    if validation['high_risk_block']: raise HTTPException(409,detail={'code':'QMS_CONSISTENCY_BLOCK'})
    # Export allowlisted structural metadata, never uncontrolled descriptions or imaging data.
    sources={
        'requirements.json':(legacy.TestRequirement,['id','requirement_id']),
        'risk-register.json':(legacy.AIRisk,['id','residual_risk']),
        'test-scenarios.json':(legacy.TestScenario,['id','test_id','scenario_type']),
        'test-results.json':(legacy.TestExecution,['id','scenario_id','status','executed_at']),
        'defects.json':(legacy.DefectRecord,['id','execution_id','status']),
        'capa.json':(legacy.OperationalCapa,['id','status']),
        'change-requests.json':(ChangeRequest,['id','change_id','status']),
        'approvals.json':(ElectronicApproval,['id','target_type','target_id','target_version','content_sha256','signature_status']),
        'model-releases.json':(legacy.ModelRelease,['id','status']),
        'model-validation.json':(legacy.ModelValidationRun,['id']),
        'monitoring-summary.json':(legacy.MonitoringSnapshot,['id','status']),
        'drift-evaluations.json':(legacy.DriftEvaluation,['id','status']),
        'security-events.json':(legacy.SecurityEvent,['id']),
    }
    files={name:canonical([{key:getattr(r,key) for key in fields} for r in db.scalars(select(model))]).encode() for name,(model,fields) in sources.items()}
    files['traceability-matrix.json']=canonical([{k:r[k] for k in ('id','source_type','source_id','target_type','target_id','version','integrity_status')} for r in links(db)]).encode()
    files['integration-tests.json']=canonical({'status':'NOT_VERIFIED','actual_external_connections':False}).encode()
    files['audit-chain-status.json']=canonical(chain).encode()
    files['README.txt']='INCOMPLETE_DRAFT — Metadata-only research QMS snapshot. Not a submission dossier. QA/RA review required; no legal signature or certification claim.'.encode()
    timestamp=datetime.now(timezone.utc).isoformat()
    manifest={'qms':True,'status':'INCOMPLETE_DRAFT','generated_at':timestamp,'generated_by_role':p.role,
        'application_version':'0.1.0','model_version':'NOT_VERIFIED','dataset_version':'NOT_VERIFIED',
        'document_version':'MULTIPLE_DRAFTS','consistency_validation_run_id':validation_run_id,'audit_chain_status':chain['status'],
        'files':[{'filename':n,'sha256':digest(b),'generated_at':timestamp,'generated_by_role':p.role} for n,b in files.items()]}
    files['manifest.json']=canonical(manifest).encode()
    output=BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items(): archive.writestr(name,data)
    return output.getvalue(),manifest

def verify_package(row):
    try:
        payload=base64.b64decode(row.payload_base64,validate=True)
        if digest(payload)!=row.package_sha256: raise ValueError()
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            manifest=json.loads(archive.read('manifest.json'))
            if manifest!=row.manifest: raise ValueError()
            expected={f['filename'] for f in manifest['files']}|{'manifest.json'}
            if set(archive.namelist())!=expected or len(archive.namelist())!=len(expected): raise ValueError()
            for item in manifest['files']:
                if digest(archive.read(item['filename']))!=item['sha256']: raise ValueError()
        return payload
    except Exception:
        raise HTTPException(409,detail={'code':'PACKAGE_INTEGRITY_FAILED'})

@router.post('/audit-packages',status_code=201)
def build_package(p=Depends(access({'QA_RA'})),db: Session=Depends(get_db)):
    from app.main import _save_consistency
    result=_save_consistency(db,'QMS','AuditPackage','DRAFT',evidence_context(db),['QMS'])
    payload,manifest=package_bytes(db,p,result['validation_run_id'])
    row=legacy.AuditPackage(created_by_role=p.role,manifest=manifest,payload_base64=base64.b64encode(payload).decode(),package_sha256=digest(payload),status='INCOMPLETE_DRAFT')
    db.add(row);db.flush()
    db.add(AuditEvidence(evidence_id='PKG-'+uuid.uuid4().hex,evidence_type='QMS_PACKAGE',related_type='AuditPackage',related_id=row.id,
        filename='qms-'+row.id+'.zip',sha256=row.package_sha256,storage_status='DATABASE',generated_by=p.role))
    save(db,row,p,'PACKAGE_CREATED')
    return {'id':row.id,'status':row.status,'sha256':row.package_sha256,'manifest':manifest}

@router.get('/audit-packages')
def packages(p=Depends(access({'QA_RA','ADMIN'})),db: Session=Depends(get_db)):
    return [{'id':r.id,'status':r.status,'sha256':r.package_sha256} for r in db.scalars(select(legacy.AuditPackage)) if r.manifest.get('qms')]

@router.get('/audit-packages/{package_id}')
def package_detail(package_id: str,p=Depends(access({'QA_RA','ADMIN'})),db: Session=Depends(get_db)):
    row=get(db,legacy.AuditPackage,package_id)
    if not row.manifest.get('qms'): raise HTTPException(404,detail={'code':'RESOURCE_NOT_FOUND'})
    verify_package(row)
    return {'id':row.id,'status':row.status,'manifest':row.manifest,'sha256':row.package_sha256}

@router.get('/audit-packages/{package_id}/download')
def download(package_id: str,p=Depends(access({'QA_RA','ADMIN'})),db: Session=Depends(get_db)):
    row=get(db,legacy.AuditPackage,package_id)
    if not row.manifest.get('qms'): raise HTTPException(404,detail={'code':'RESOURCE_NOT_FOUND'})
    if verify_chain(db)['status']=='INTEGRITY_FAILED': raise HTTPException(409,detail={'code':'AUDIT_INTEGRITY_FAILED'})
    payload=verify_package(row)
    return Response(payload,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename=qms-{row.id}.zip'})
