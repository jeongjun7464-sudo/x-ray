# 문서관리 절차

문서번호: QMS-DCP-001 · 버전: 0.1 · 상태: DRAFT

작성자 역할: 개발 지원 · 검토자 역할: QA_RA · 승인 상태: 미승인 · 발효일: 없음

내용 SHA-256: phase30-document-manifest.json의 파일별 값 참조

관련 요구사항: REQ-QMS-02 · 관련 위험: R-QMS-INTEGRITY · 관련 시험: backend/tests/test_phase30_workflows.py, backend/tests/test_phase30_draft.py

## 절차 및 구현

문서는 DRAFT로 생성한다. 변경은 기존 버전 덮어쓰기가 아닌 new-version으로 등록한다. 검토 요청 → 독립 검토 → APPROVAL_REQUIRED까지 기록하며 재인증 미설정 때문에 승인과 발효는 차단한다. 버전 번호 충돌은 409로 거부한다.

## 검토 필요 사항

다운로드 전에 콘텐츠 SHA-256을 검증한다. 승인·발효 상태에는 승인 버전과 해시도 요구한다. 이전 버전은 보존하며 새 버전의 승인 상태를 이전 버전에서 상속하지 않는다. 생성 콘텐츠 검사는 휴리스틱이므로 개인정보 부재나 근거 타당성을 완전 보장하지 않으며 수동 검토가 필요하다.

이 문서는 연구·교육용 초안이며 규제기관 승인·표준 인증·법적 전자서명 적합성을 보장하지 않는다. 전체 구현 범위와 시험 기록은 [Phase 30 상태](phase30-qms-regulatory-traceability.md)를 참조한다.
