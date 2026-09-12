import re
from fastapi import HTTPException

AMBIGUOUS = ('빠르게', '적절하게', '가능하면', '충분히', '사용하기 쉽게', '높은 성능', '안전하게')
def ambiguity(text):
    return [{'phrase': term, 'suggestion': '측정 기준·조건·허용 범위를 명시하세요.'} for term in AMBIGUOUS if term in text]

def validate_text(text):
    # Heuristic rejection is not proof that all PHI has been removed.
    patterns = (r'\b\d{6}[- ]?[1-4]\d{6}\b', r'01[016789][- ]?\d{3,4}[- ]?\d{4}',
        r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', r'(?i)(PatientName|PatientID|주민등록번호|환자명|전화번호|주소)\s*[:=]',
        r'(?i)(api[_-]?key|password|secret|authorization)\s*[:=]\s*\S+')
    if any(re.search(pattern, text) for pattern in patterns):
        raise HTTPException(422, detail={'code': 'SENSITIVE_CONTENT_BLOCKED'})
    if re.search(r'(?:미측정|NOT_MEASURED|NO_EVIDENCE).{0,30}\bPASS\b', text, re.I):
        raise HTTPException(422, detail={'code': 'UNMEASURED_PASS_BLOCKED'})
    if any(term in text for term in ('인증을 자동 보장', '법적 전자서명 충족', '규제 적합성 PASS')):
        raise HTTPException(422, detail={'code': 'UNVERIFIED_REGULATORY_CLAIM'})
    return {'status': 'MANUAL_REVIEW_REQUIRED', 'privacy_scan': 'HEURISTIC_ONLY'}
