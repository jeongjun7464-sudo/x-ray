import re
PATTERNS=[re.compile(r"\b\d{6}[- ]?[1-4]\d{6}\b"),re.compile(r"\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b"),re.compile(r"(?i)(patientname|patientid|환자명|주민등록번호|주소)\s*[:=]\s*\S+")]
def contains_phi(text):return any(x.search(text) for x in PATTERNS)
def validate_document(text):
    if contains_phi(text):raise ValueError("PHI_DETECTED: 개인정보가 포함된 문서는 색인할 수 없습니다.")
    if "api_key:" in text.lower() or "authorization: bearer" in text.lower():raise ValueError("SECRET_DETECTED: 비밀값이 포함된 문서는 색인할 수 없습니다.")
