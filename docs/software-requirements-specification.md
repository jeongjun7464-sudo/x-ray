# 소프트웨어 요구사항 명세

문서번호: QMS-SRS-001 · 버전: 0.1 · 상태: DRAFT

작성자 역할: 개발 지원 · 검토자 역할: QA_RA · 승인 상태: 미승인 · 발효일: 없음

내용 SHA-256: phase30-document-manifest.json의 파일별 값 참조

관련 요구사항: REQ-QMS-01 · 관련 위험: R-QMS-INTEGRITY · 관련 시험: backend/tests/test_phase30_workflows.py, backend/tests/test_phase30_draft.py

## 절차 및 구현

REQ-QMS-01: 인증된 QA_RA 또는 허용된 개발자만 QMS 레코드를 작성할 수 있다. REQ-QMS-02: 독립 승인과 정확한 버전·해시 확인 없이 문서 발효와 중요 승인을 성공 처리하지 않는다. REQ-QMS-03: 존재하지 않는 추적성 대상은 409로 거부한다.

## 검토 필요 사항

REQ-QMS-04: 문서·패키지 해시 또는 감사 체인 불일치를 탐지하여 보호 작업을 차단한다. REQ-QMS-05: 근거 없는 수치와 승인 상태를 만들지 않는다. REQ-QMS-06: 원본 환자 영상과 개인정보를 QMS 자료로 사용하지 않는다. 각 요구사항의 단위 시험은 phase30 추적성 부록에서 연결한다.

이 문서는 연구·교육용 초안이며 규제기관 승인·표준 인증·법적 전자서명 적합성을 보장하지 않는다. 전체 구현 범위와 시험 기록은 [Phase 30 상태](phase30-qms-regulatory-traceability.md)를 참조한다.
