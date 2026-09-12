"""Institution-scoped integration API. No public route executes external writes."""
import hashlib
import re
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.auth import current_principal
from app.core.config import settings
from app.db.database import get_db
from app.db.models import XrayAnalysis, SecurityEvent
from app.db.integration_models import InstitutionConnection, ExternalTransferJob, ExternalTransferEvent, FhirExportRecord
from app.services.audit import record_audit
from .schemas import AdapterConfig
from .orthanc import OrthancAdapter
from .dicomweb import DicomWebAdapter
from .fhir import FhirAdapter, create_bundle, validate_resource
from .security import masked_endpoint

router = APIRouter(prefix="/api/v1", tags=["Medical integration"])
ROLES = {"TECHNICIAN", "RADIOLOGIST", "QA_RA", "ADMIN"}

def access(roles=ROLES):
    def dependency():
        principal = current_principal()
        if principal is None:
            raise HTTPException(401, detail={"code": "AUTHENTICATION_REQUIRED"})
        if principal.role not in roles:
            raise HTTPException(403, detail={"code": "AUTHORIZATION_DENIED"})
        institution = settings.integration_principal_institutions.get(principal.subject)
        if not institution or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", institution):
            raise HTTPException(403, detail={"code": "INSTITUTION_MAPPING_REQUIRED"})
        return principal, institution
    return dependency

def adapters():
    common = dict(production=settings.environment.lower() in {"prod", "production"},
                  transmission_enabled=settings.external_transmission_enabled,
                  allow_demo_transmission=settings.external_transmission_allow_demo)
    return {
        "ORTHANC": OrthancAdapter(AdapterConfig(base_url=settings.orthanc_base_url,
            enabled=settings.pacs_enabled and settings.pacs_provider=="orthanc", verify_tls=settings.orthanc_verify_tls,
            username=settings.orthanc_username, password=settings.orthanc_password, timeout=settings.orthanc_timeout_seconds, **common)),
        "DICOMWEB": DicomWebAdapter(AdapterConfig(base_url=settings.dicomweb_base_url,
            enabled=settings.pacs_enabled and settings.pacs_provider=="dicomweb", verify_tls=settings.dicomweb_verify_tls,
            token=settings.dicomweb_token, timeout=settings.dicomweb_timeout_seconds, **common)),
        "FHIR": FhirAdapter(AdapterConfig(base_url=settings.fhir_base_url, enabled=settings.fhir_enabled,
            verify_tls=settings.fhir_verify_tls, token=settings.fhir_token, timeout=settings.fhir_timeout_seconds, **common))}

class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_id: str = Field(min_length=1, max_length=64)
    destination: str = Field(pattern="^(FHIR|ORTHANC|DICOMWEB)$")
    reason: str = Field(min_length=3, max_length=200)

class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool
    reason: str = Field(min_length=3, max_length=200)

def scoped_analysis(db, analysis_id, institution):
    if settings.integration_resource_institutions.get(analysis_id) != institution:
        raise HTTPException(404, detail={"code": "RESOURCE_NOT_FOUND"})
    row = db.get(XrayAnalysis, analysis_id)
    if row is None: raise HTTPException(404, detail={"code": "RESOURCE_NOT_FOUND"})
    return row

def scoped_job(db, job_id, institution):
    row = db.scalar(select(ExternalTransferJob).where(ExternalTransferJob.id==job_id, ExternalTransferJob.institution_id==institution))
    if row is None: raise HTTPException(404, detail={"code": "RESOURCE_NOT_FOUND"})
    return row

def job_out(row):
    return {key: getattr(row, key) for key in ("id", "institution_id", "transfer_type", "resource_type", "resource_id", "destination",
        "status", "attempt_count", "max_attempts", "failure_code", "next_attempt_at", "created_at")}

def audit(db, row, request, who, event, reason):
    rid = hashlib.sha256(request.headers.get("X-Request-ID", str(uuid.uuid4())).encode()).hexdigest()
    # Store a reason digest instead of unscreened free text.
    detail = {"reason_sha256": hashlib.sha256(reason.encode()).hexdigest()}
    db.add(ExternalTransferEvent(transfer_job_id=row.id, event_type=event, request_id=rid, status=row.status, event_metadata=detail))
    record_audit(db, action=event, request_id=rid, target_id=row.id, actor_id=who.subject, actor_role=who.role,
                 after={"status": row.status, **detail})

@router.get("/integrations/capabilities")
def capabilities(identity=Depends(access())):
    return {"status": "PARTIAL", "external_transmission": "BLOCKED_PENDING_VALIDATION",
        "operations": ["health-check", "study-search", "fhir-preview", "proposal", "confirm", "cancel"],
        "institution_id": identity[1], "full_fhir_validator": "NOT_CONFIGURED"}

@router.post("/integrations/health-check")
def health(request: Request, identity=Depends(access({"QA_RA", "ADMIN"})), db: Session=Depends(get_db)):
    output = {}
    for provider, adapter in adapters().items():
        result = adapter.health_check()
        row = InstitutionConnection(institution_id=identity[1], connection_type=provider, provider=provider,
            base_url_masked=masked_endpoint(adapter.config.base_url), status=result.status, capabilities={},
            enabled=adapter.config.enabled, tls_verification=adapter.config.verify_tls,
            last_health_check_at=datetime.now(timezone.utc),
            last_success_at=datetime.now(timezone.utc) if result.status=="CONNECTED" else None, last_error_code=result.code)
        db.add(row)
        output[provider] = {"status": result.status, "code": result.code, "mode": result.mode}
    record_audit(db, action="INTEGRATION_HEALTH_CHECK", request_id=uuid.uuid4().hex,
                actor_id=identity[0].subject, actor_role=identity[0].role, after=output)
    db.commit()
    return output

@router.get("/integrations/connections")
def connections(identity=Depends(access({"QA_RA", "ADMIN"})), db: Session=Depends(get_db)):
    rows = db.scalars(select(InstitutionConnection).where(InstitutionConnection.institution_id==identity[1]).order_by(InstitutionConnection.created_at.desc()).limit(30))
    return [{"id": r.id, "provider": r.provider, "status": r.status, "last_health_check_at": r.last_health_check_at,
        "tls_verification": r.tls_verification, "last_error_code": r.last_error_code} for r in rows]

class Search(BaseModel):
    model_config = ConfigDict(extra="forbid")
    StudyDate: str = Field(default="", pattern=r"^[0-9-]{0,17}$")
    Modality: str = Field(default="", pattern=r"^(|DX|CR|CT|MR|US)$")
    BodyPartExamined: str = Field(default="", pattern=r"^[A-Z_]{0,32}$")
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

@router.post("/dicomweb/studies/search")
def search(body: Search, identity=Depends(access({"TECHNICIAN", "RADIOLOGIST", "ADMIN"}))):
    if identity[1] != settings.integration_connection_institution_id:
        raise HTTPException(403, detail={"code": "CONNECTION_INSTITUTION_MISMATCH"})
    result = adapters()["DICOMWEB"].qido_search(body.model_dump(exclude_defaults=True))
    return asdict(result)

@router.get("/xray/analyses/{analysis_id}/fhir")
def preview(analysis_id: str, identity=Depends(access()), db: Session=Depends(get_db)):
    row = scoped_analysis(db, analysis_id, identity[1])
    info = row.model_info
    bundle = create_bundle(row.id, row.region_result.get("code", "UNKNOWN"), str(info.get("region_model_version", "UNKNOWN")), str(info.get("dataset_version", "UNKNOWN")))
    return {"bundle": bundle, "validation": validate_resource(bundle), "research_only": True}

@router.post("/xray/analyses/{analysis_id}/fhir/validate")
def validate(analysis_id: str, identity=Depends(access()), db: Session=Depends(get_db)):
    result = preview(analysis_id, identity, db)
    v = result["validation"]
    db.add(FhirExportRecord(institution_id=identity[1], analysis_id=analysis_id, bundle_type="collection",
        bundle_sha256=v["bundle_sha256"], validation_status=v["status"], transmission_status="NOT_TRANSMITTED",
        destination="FHIR", created_by=identity[0].subject))
    db.commit()
    return v

@router.get("/fhir/exports")
def exports(identity=Depends(access()), db: Session=Depends(get_db)):
    return [{"id": r.id, "analysis_id": r.analysis_id, "validation_status": r.validation_status,
        "transmission_status": r.transmission_status, "bundle_sha256": r.bundle_sha256}
        for r in db.scalars(select(FhirExportRecord).where(FhirExportRecord.institution_id==identity[1]))]

@router.post("/external-transfers/proposals", status_code=201)
def propose(body: Proposal, request: Request, idempotency_key: str=Header(alias="Idempotency-Key", min_length=1, max_length=100),
            identity=Depends(access({"RADIOLOGIST", "QA_RA", "ADMIN"})), db: Session=Depends(get_db)):
    scoped_analysis(db, body.analysis_id, identity[1])
    previous = db.scalar(select(ExternalTransferJob).where(ExternalTransferJob.institution_id==identity[1], ExternalTransferJob.idempotency_key==idempotency_key))
    if previous:
        if previous.resource_id != body.analysis_id or previous.destination != body.destination:
            raise HTTPException(409, detail={"code": "IDEMPOTENCY_CONFLICT"})
        return job_out(previous)
    row = ExternalTransferJob(institution_id=identity[1], transfer_type="FHIR" if body.destination=="FHIR" else "DICOM_SR",
        resource_type="XrayAnalysis", resource_id=body.analysis_id, destination=body.destination,
        idempotency_key=idempotency_key, created_by=identity[0].subject, max_attempts=settings.external_max_retries)
    db.add(row)
    try:
        db.flush()
        audit(db, row, request, identity[0], "TRANSFER_PROPOSED", body.reason)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail={"code": "CONCURRENT_PROPOSAL_RETRY"})
    return job_out(row)

@router.get("/external-transfers")
def jobs(identity=Depends(access()), db: Session=Depends(get_db)):
    return [job_out(r) for r in db.scalars(select(ExternalTransferJob).where(ExternalTransferJob.institution_id==identity[1]))]

@router.get("/external-transfers/{job_id}")
def get_job(job_id: str, identity=Depends(access()), db: Session=Depends(get_db)):
    return job_out(scoped_job(db, job_id, identity[1]))

@router.post("/external-transfers/{job_id}/confirm")
def confirm(job_id: str, body: Confirmation, request: Request, identity=Depends(access({"RADIOLOGIST", "QA_RA", "ADMIN"})), db: Session=Depends(get_db)):
    row = scoped_job(db, job_id, identity[1])
    if row.status != "AWAITING_CONFIRMATION": raise HTTPException(409, detail={"code": "TRANSFER_STATE_CONFLICT"})
    if not body.confirmed: raise HTTPException(422, detail={"code": "EXPLICIT_CONFIRMATION_REQUIRED"})
    analysis = scoped_analysis(db, row.resource_id, identity[1])
    reasons = []
    if not settings.external_transmission_enabled: reasons.append("TRANSMISSION_DISABLED")
    if not analysis.reviewed: reasons.append("CLINICIAN_REVIEW_REQUIRED")
    if analysis.model_info.get("dummy_mode", True): reasons.append("MODEL_NOT_APPROVED")
    # Complete FHIR, SR and model-binding validation is not installed.
    reasons.append("INTEGRATION_VALIDATION_NOT_CONFIGURED")
    row.status = "MANUAL_REVIEW_REQUIRED"
    row.failure_code = reasons[0]
    audit(db, row, request, identity[0], "TRANSFER_BLOCKED", body.reason)
    from app.main import _save_consistency
    _save_consistency(db, "MEDICAL_INTEGRATION", "ExternalTransferJob", row.id, {"integration": {
        "institution_matches": row.institution_id == identity[1],
        "transmission_enabled": settings.external_transmission_enabled,
        "approved_model": False,
        "clinician_reviewed": analysis.reviewed,
        "confirmed": body.confirmed,
        "idempotency_present": bool(row.idempotency_key),
        "audit_present": True,
        "deployment_binding_matches": False,
    }}, ["MEDICAL_INTEGRATION"])
    db.add(SecurityEvent(event_type="EXTERNAL_TRANSFER_BLOCKED", request_id=uuid.uuid4().hex, details={"job_id": row.id, "reason_codes": reasons}))
    db.commit()
    return JSONResponse(status_code=409, content={"status": row.status, "reason_codes": reasons, "transmitted": False})

@router.post("/external-transfers/{job_id}/cancel")
def cancel(job_id: str, body: Confirmation, request: Request, identity=Depends(access({"RADIOLOGIST", "QA_RA", "ADMIN"})), db: Session=Depends(get_db)):
    row = scoped_job(db, job_id, identity[1])
    if row.status not in {"AWAITING_CONFIRMATION", "MANUAL_REVIEW_REQUIRED", "RETRY_PENDING"}:
        raise HTTPException(409, detail={"code": "TRANSFER_STATE_CONFLICT"})
    row.status = "CANCELLED"; row.completed_at = datetime.now(timezone.utc)
    audit(db, row, request, identity[0], "TRANSFER_CANCELLED", body.reason)
    db.commit()
    return job_out(row)

@router.post("/external-transfers/{job_id}/retry")
def retry(job_id: str, identity=Depends(access({"ADMIN"})), db: Session=Depends(get_db)):
    row = scoped_job(db, job_id, identity[1])
    raise HTTPException(409, detail={"code": "TRANSFER_WORKER_NOT_CONFIGURED", "status": row.status})
