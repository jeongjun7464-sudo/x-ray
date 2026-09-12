"""Tamper-evident, not tamper-proof. No external trusted anchor is configured."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from app.db.models import AuditEvent
from app.db.qms_models import AuditChainEntry

def canonical(value): return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)
def digest(value): return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()
def payload(row):
    # Only digests of uncontrolled text are included in the chain API.
    fields = {key: getattr(row, key) for key in ('id', 'actor_id', 'actor_role', 'action',
        'target_id', 'before_value', 'after_value', 'request_id', 'reason')}
    stamp = row.created_at
    fields['created_at'] = stamp.replace(tzinfo=timezone.utc).isoformat() if stamp and stamp.tzinfo is None else stamp.astimezone(timezone.utc).isoformat() if stamp else None
    return canonical(fields)

@event.listens_for(Session, 'before_flush')
def chain_new_events(db, context, instances):
    for row in db.dirty.union(db.deleted):
        if isinstance(row, AuditEvent) and (row in db.deleted or db.is_modified(row)):
            raise ValueError('APPEND_ONLY_AUDIT_EVENT')
    pending = [r for r in db.new if isinstance(r, AuditEvent)]
    if not pending: return
    # Concurrent append conflicts fail the transaction (unique sequence), never fork silently.
    last = db.scalar(select(AuditChainEntry).order_by(AuditChainEntry.sequence.desc()).limit(1))
    sequence, previous = (last.sequence, last.event_hash) if last else (0, '0' * 64)
    for row in pending:
        row.id = row.id or str(uuid.uuid4())
        row.actor_id = row.actor_id or 'anonymous'; row.actor_role = row.actor_role or 'USER'
        row.created_at = row.created_at or datetime.now(timezone.utc)
        sequence += 1
        text = payload(row)
        hashed = digest(previous + text + str(sequence))
        db.add(AuditChainEntry(sequence=sequence, event_id=row.id, previous_hash=previous,
            event_hash=hashed, payload_hash=digest(text)))
        previous = hashed

def verify_chain(db):
    entries = db.scalars(select(AuditChainEntry).order_by(AuditChainEntry.sequence)).all()
    previous = '0' * 64; errors = []; covered = set()
    for expected, entry in enumerate(entries, 1):
        row = db.get(AuditEvent, entry.event_id); covered.add(entry.event_id)
        if row is None or entry.sequence != expected or entry.previous_hash != previous:
            errors.append({'sequence': entry.sequence, 'code': 'CHAIN_GAP'})
        if row and (entry.payload_hash != digest(payload(row)) or
                    entry.event_hash != digest(entry.previous_hash + payload(row) + str(entry.sequence))):
            errors.append({'sequence': entry.sequence, 'code': 'HASH_MISMATCH'})
        previous = entry.event_hash
    unchained = len(set(db.scalars(select(AuditEvent.id))) - covered)
    return {'status': 'INTEGRITY_FAILED' if errors else ('NOT_VERIFIED' if unchained or not entries else 'VERIFIED'),
        'entries': len(entries), 'unchained_events': unchained, 'errors': errors,
        'head_hash': previous, 'external_anchor': 'NOT_CONFIGURED', 'tamper_proof': False}
