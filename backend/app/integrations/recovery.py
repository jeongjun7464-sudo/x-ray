"""Bounded recovery bookkeeping; does not dispatch network traffic."""
from datetime import datetime, timedelta, timezone
from .retry import retry_delay
from app.db.integration_models import ExternalTransferEvent
from app.db.models import SecurityEvent

NON_RETRYABLE = {"AUTH_FAILED", "TLS_ERROR", "TRANSMISSION_DISABLED", "VALIDATION_FAILED",
                 "CONFIRMATION_REQUIRED", "PHI_DETECTED", "INSTITUTION_MISMATCH"}

def record_failure(db, job, result, request_id, *, upstream_idempotency_verified=False, now=None):
    now = now or datetime.now(timezone.utc)
    if job.status != "SENDING":
        raise ValueError("TRANSFER_NOT_SENDING")
    job.failure_code = result.code
    job.response_status = result.http_status
    job.failure_message = "External transfer failed; inspect the structured failure code."
    prohibited = result.http_status in {400, 401, 403} or result.status == "CERTIFICATE_ERROR"
    prohibited = prohibited or any((result.code or "").endswith(code) for code in NON_RETRYABLE)
    delay = retry_delay(job.attempt_count, job.max_attempts)
    job.next_attempt_at = None
    if result.retryable and not prohibited and upstream_idempotency_verified and delay is not None:
        job.status = "RETRY_PENDING"
        job.next_attempt_at = now + timedelta(seconds=delay)
    elif result.retryable and not prohibited and not upstream_idempotency_verified:
        # A lost response cannot safely be retried without receiver deduplication.
        job.status = "MANUAL_REVIEW_REQUIRED"
    else:
        job.status = "QUARANTINED"
    db.add(ExternalTransferEvent(transfer_job_id=job.id, event_type="TRANSFER_FAILURE",
        request_id=request_id, status=job.status,
        event_metadata={"failure_code": job.failure_code, "attempt_count": job.attempt_count}))
    if job.status == "QUARANTINED":
        db.add(SecurityEvent(event_type="TRANSFER_QUARANTINED", request_id=request_id,
            details={"job_id": job.id, "failure_code": job.failure_code}))
    return job.status
