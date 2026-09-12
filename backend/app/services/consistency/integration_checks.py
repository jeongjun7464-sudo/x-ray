from .base import ConsistencyRule
from .registry import register

# Stable IDs: institution matching is INT-004; INT-007 is model approval.
DEFINITIONS = (
    ("INT-001", "configuration_matches_enabled", "PACS 설정과 활성 상태", "HIGH"),
    ("INT-002", "tls_verified", "TLS 검증", "CRITICAL"),
    ("INT-003", "transmission_enabled", "외부 전송 기능 활성화", "HIGH"),
    ("INT-004", "institution_matches", "기관 일치", "CRITICAL"),
    ("INT-005", "deidentified", "DICOM 비식별화", "CRITICAL"),
    ("INT-006", "pixel_reviewed", "Burned-in text 검토", "HIGH"),
    ("INT-007", "approved_model", "모델 승인", "CRITICAL"),
    ("INT-008", "clinician_reviewed", "의료진 검토", "HIGH"),
    ("INT-009", "sr_model_matches", "SR 모델 정보", "HIGH"),
    ("INT-010", "fhir_references_valid", "FHIR 참조", "CRITICAL"),
    ("INT-011", "phi_free", "개인정보 검사", "CRITICAL"),
    ("INT-012", "confirmed", "사용자 명시적 확인", "CRITICAL"),
    ("INT-013", "idempotency_present", "멱등 키", "HIGH"),
    ("INT-014", "retry_policy_valid", "재시도 정책", "HIGH"),
    ("INT-015", "audit_present", "전송 감사 기록", "CRITICAL"),
    ("INT-016", "study_mapping_valid", "Study 매핑", "HIGH"),
    ("INT-017", "uid_hash_matches", "UID 해시", "HIGH"),
    ("INT-018", "deployment_binding_matches", "배포 모델과 전송 모델", "CRITICAL"),
)

def build(rule_id, key, label, severity):
    def check(self, context):
        evidence = context.get("integration", {})
        value = evidence.get(key)
        if value is None:
            return self.finding("NOT_VERIFIABLE", label + " 증적 없음", action="BLOCK_EXTERNAL_TRANSFER", review=True)
        ok = value is True
        return self.finding("PASS" if ok else "FAIL", label, True, value,
            action="NONE" if ok else "BLOCK_EXTERNAL_TRANSFER", review=not ok)
    return type(rule_id.replace("-", "_"), (ConsistencyRule,), {
        "rule_id": rule_id, "category": "MEDICAL_INTEGRATION", "severity": severity, "check": check})
for definition in DEFINITIONS:
    register(build(*definition))
