"""No client-supplied reauthentication assertion or demo bypass is accepted."""
from fastapi import HTTPException

MEANINGS = {'REVIEWED', 'APPROVED', 'RELEASE_AUTHORIZED', 'EFFECTIVENESS_CONFIRMED',
            'RISK_ACCEPTED', 'DOCUMENT_EFFECTIVE'}

def require_electronic_approval(principal, author, version, current_version, meaning, reason):
    if principal is None: raise HTTPException(401, detail={'code': 'AUTHENTICATION_REQUIRED'})
    if principal.subject == author: raise HTTPException(409, detail={'code': 'SEPARATION_OF_DUTIES_REQUIRED'})
    if version != current_version: raise HTTPException(409, detail={'code': 'VERSION_CONFLICT'})
    if meaning not in MEANINGS or not reason.strip():
        raise HTTPException(422, detail={'code': 'APPROVAL_MEANING_AND_REASON_REQUIRED'})
    raise HTTPException(409, detail={'code': 'REAUTHENTICATION_NOT_CONFIGURED',
        'approved': False, 'legal_signature_compliance': 'NOT_VERIFIED'})
