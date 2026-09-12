# 소프트웨어 개발 계획

문서번호: QMS-SDP-001 · 버전: 0.1 · 상태: DRAFT

작성자 역할: 개발 지원 · 검토자 역할: QA_RA · 승인 상태: 미승인 · 발효일: 없음

내용 SHA-256: phase30-document-manifest.json의 파일별 값 참조

관련 요구사항: REQ-QMS-01 · 관련 위험: R-QMS-INTEGRITY · 관련 시험: backend/tests/test_phase30_workflows.py, backend/tests/test_phase30_draft.py

## 절차 및 구현

인증 세션과 기존 저장 모델을 재사용한다. Phase 30은 별도 개발 브랜치에서 마이그레이션 → API → 화면 → 합성 시험 → 독립 검토 순서로 개발한다. 생성 에이전트는 읽기와 초안 생성만 수행한다.

## 검토 필요 사항

종료 기준은 요구사항별 시험, 변경 영향평가, 실패 공개, 이전 기능 회귀 확인이다. 현재 재인증과 운영 승인 환경이 없으므로 운영 릴리스 승인은 금지한다. 의존 패키지 고정·PostgreSQL·실제 기관 통합 시험은 별도로 확인한다.

이 문서는 연구·교육용 초안이며 규제기관 승인·표준 인증·법적 전자서명 적합성을 보장하지 않는다. 전체 구현 범위와 시험 기록은 [Phase 30 상태](phase30-qms-regulatory-traceability.md)를 참조한다.
