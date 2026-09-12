# 위험관리 보고서 초안

문서번호: QMS-RMR-001 · 버전: 0.1 · 상태: DRAFT

작성자 역할: 개발 지원 · 검토자 역할: QA_RA · 승인 상태: 미승인 · 발효일: 없음

내용 SHA-256: phase30-document-manifest.json의 파일별 값 참조

관련 요구사항: REQ-QMS-04 · 관련 위험: R-QMS-INTEGRITY · 관련 시험: backend/tests/test_phase30_workflows.py, backend/tests/test_phase30_draft.py

## 절차 및 구현

평가 대상은 잘못된 승인, 문서 변조, 감사 로그 누락, 개인정보 포함, 근거 없는 생성 결과, 미승인 모델·변경 배포다. QMS-009/010/012/017/018/020 등의 실패는 사람 검토와 중요 작업 차단으로 연결한다.

## 검토 필요 사항

현재 실제 제품의 위험 수용 판단, 임상 성능, 전체 조직 운영 통제의 유효성은 NOT_VERIFIED다. 작성자는 위험대장과 시험 증적을 보완하고 QA_RA의 독립 검토를 받아야 한다. 이 초안은 위험 수용 보고서가 아니다.

이 문서는 연구·교육용 초안이며 규제기관 승인·표준 인증·법적 전자서명 적합성을 보장하지 않는다. 전체 구현 범위와 시험 기록은 [Phase 30 상태](phase30-qms-regulatory-traceability.md)를 참조한다.
