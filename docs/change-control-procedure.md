# 변경관리 절차

문서번호: QMS-CCP-001 · 버전: 0.1 · 상태: DRAFT

작성자 역할: 개발 지원 · 검토자 역할: QA_RA · 승인 상태: 미승인 · 발효일: 없음

내용 SHA-256: phase30-document-manifest.json의 파일별 값 참조

관련 요구사항: REQ-QMS-03 · 관련 위험: R-QMS-INTEGRITY · 관련 시험: backend/tests/test_phase30_workflows.py, backend/tests/test_phase30_draft.py

## 절차 및 구현

변경요청에 영향을 받는 요구사항·위험·시험·모델·데이터셋·연동을 등록한다. HIGH 영향평가에는 FULL_REGRESSION 범위를 포함해야 한다. 영향평가 후 REVIEW_REQUIRED로 이동한다. 임의 상태 문자열 수정은 허용하지 않는다.

## 검토 필요 사항

승인에는 독립 사용자와 재인증이 필요하다. 재인증 미설정 상태에서 승인·배포를 완료할 수 없다. 관련 미완료 변경이나 HIGH/CRITICAL CAPA가 있는 모델은 QMS Release Gate에서 차단한다. 레거시 배포 절차 전체의 운영 승인 전환은 아직 추가 검증이 필요하다.

이 문서는 연구·교육용 초안이며 규제기관 승인·표준 인증·법적 전자서명 적합성을 보장하지 않는다. 전체 구현 범위와 시험 기록은 [Phase 30 상태](phase30-qms-regulatory-traceability.md)를 참조한다.
