# 전자승인 정책

문서번호: QMS-EAP-001 · 버전: 0.1 · 상태: DRAFT

작성자 역할: 개발 지원 · 검토자 역할: QA_RA · 승인 상태: 미승인 · 발효일: 없음

내용 SHA-256: phase30-document-manifest.json의 파일별 값 참조

관련 요구사항: REQ-QMS-02 · 관련 위험: R-QMS-INTEGRITY · 관련 시험: backend/tests/test_phase30_workflows.py, backend/tests/test_phase30_draft.py

## 절차 및 구현

승인 대상, 버전, 콘텐츠 SHA-256, 의미, 사유, 인증 방식, 요청 ID 및 서명자를 기록하는 데이터 구조를 제공한다. 작성자와 승인자를 서버에서 분리한다. 클라이언트가 보내는 재인증 성공 플래그는 근거로 인정하지 않는다.

## 검토 필요 사항

현재 재인증 제공자가 없어 모든 중요 승인 성공 경로는 REAUTHENTICATION_NOT_CONFIGURED로 차단된다. 데모 우회는 제공하지 않는다. 승인·검토 기록에는 일반 수정·삭제 API가 없고 ORM 변경도 거부한다. 직접 DB 관리자 접근은 별도 통제가 필요하다. 법적 전자서명 충족 여부는 NOT_VERIFIED다.

이 문서는 연구·교육용 초안이며 규제기관 승인·표준 인증·법적 전자서명 적합성을 보장하지 않는다. 전체 구현 범위와 시험 기록은 [Phase 30 상태](phase30-qms-regulatory-traceability.md)를 참조한다.
