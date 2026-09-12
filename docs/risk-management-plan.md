# 위험관리 계획

문서번호: QMS-RMP-001 · 버전: 0.1 · 상태: DRAFT

작성자 역할: 개발 지원 · 검토자 역할: QA_RA · 승인 상태: 미승인 · 발효일: 없음

내용 SHA-256: phase30-document-manifest.json의 파일별 값 참조

관련 요구사항: REQ-QMS-02 · 관련 위험: R-QMS-INTEGRITY · 관련 시험: backend/tests/test_phase30_workflows.py, backend/tests/test_phase30_draft.py

## 절차 및 구현

위험 식별 → 위해 상황·발생 순서·위해 기록 → 심각도와 발생 가능성 평가 → 통제와 시험 연결 → 잔여 위험 검토 순서로 관리한다. 기본 연구용 매트릭스는 1~5의 심각도와 가능성의 곱이다. HIGH=10 이상, CRITICAL=20 이상이며 설정값을 사용한다.

## 검토 필요 사항

설계 제거, 보호조치, 안전 정보, 사람 검토, 운영 모니터링을 통제 검토 항목으로 사용한다. 점수 계산이 위험 수용을 의미하지 않는다. CRITICAL 위험은 실제 시험 증적이 필요하며 재인증이 없으면 수용 승인을 차단한다. [ISO 14971 공식 개요](https://www.iso.org/standard/72704.html)는 위험관리의 용어·원칙·프로세스를 설명하며 본 예제의 공식 적합성을 증명하지 않는다.

이 문서는 연구·교육용 초안이며 규제기관 승인·표준 인증·법적 전자서명 적합성을 보장하지 않는다. 전체 구현 범위와 시험 기록은 [Phase 30 상태](phase30-qms-regulatory-traceability.md)를 참조한다.
