# 감사 추적 무결성

문서번호: QMS-ATI-001 · 버전: 0.1 · 상태: DRAFT

작성자 역할: 개발 지원 · 검토자 역할: QA_RA · 승인 상태: 미승인 · 발효일: 없음

내용 SHA-256: phase30-document-manifest.json의 파일별 값 참조

관련 요구사항: REQ-QMS-04 · 관련 위험: R-QMS-INTEGRITY · 관련 시험: backend/tests/test_phase30_workflows.py, backend/tests/test_phase30_draft.py

## 절차 및 구현

새 AuditEvent는 canonical JSON과 이전 해시, 순번을 사용해 SHA-256 체인에 연결된다. 조회 API에는 이벤트 본문 대신 해시·순번을 제공한다. 기존 이벤트의 누락, 순번 불일치, 본문·시각 변조를 점검한다. 승인·감사 기록을 cascade delete하지 않는다.

## 검토 필요 사항

과거 미연결 로그가 있으면 NOT_VERIFIED이며 자동으로 과거 기록을 인증하지 않는다. 동시 append 충돌은 unique 제약으로 실패한다. 외부 신뢰 앵커·WORM 저장소·다중 작업자 재시도는 미구현이다. DB 관리자가 전체 체인과 이벤트를 함께 재작성하거나 꼬리를 함께 삭제하는 공격을 완전히 방지한다고 주장하지 않는다.

이 문서는 연구·교육용 초안이며 규제기관 승인·표준 인증·법적 전자서명 적합성을 보장하지 않는다. 전체 구현 범위와 시험 기록은 [Phase 30 상태](phase30-qms-regulatory-traceability.md)를 참조한다.
