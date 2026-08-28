from sqlalchemy.orm import Session
from app.db.models import AuditEvent


def record_audit(db: Session, *, action: str, request_id: str, target_id: str | None = None,
                 before: dict | None = None, after: dict | None = None, reason: str | None = None,
                 actor_id: str = "anonymous", actor_role: str = "USER") -> AuditEvent:
    event = AuditEvent(actor_id=actor_id, actor_role=actor_role, action=action, target_id=target_id,
                       before_value=before, after_value=after, request_id=request_id, reason=reason)
    db.add(event)
    return event
