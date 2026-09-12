# Changelog

## Phase 30 — QMS (unreleased / partial)

기존 시험 요구사항·위험·CAPA·결함 모델을 확장하고 0016_qms migration, QMS API·React 화면·문서 버전·양방향 추적성·감사 체인·패키지 해시 검사를 추가했습니다. 중요 전자승인은 fail-closed이며 실제 운영 승인·기관 연동은 검증되지 않았습니다. Phase 29와 함께 개발 브랜치에서 관리하며 main에 병합하지 않았습니다.

## Phase 28 — ModelOps Validation & Deployment

- Added controlled lifecycle transitions, model artifact metadata and SHA-256/signature validation.
- Added dataset lineage/leakage checks, versioned validation policies, measured-metric persistence and idempotent validation runs.
- Enforced registerer/approver/deployer separation, evidence-backed internal approval, Release Gate deployment and integrity-checked rollback.
- Added MODEL-OPS-001..016 consistency rules, ModelOps UI, migration, tests and repository artifact CI policy.

## Phase 27 — Model Monitoring & Drift

- Added versioned monitoring snapshots, approved baselines, Jensen–Shannon drift evaluation and unresolved alerts.
- Added evidence-based release blocking and repeated-warning CAPA candidates without automatic approval or deployment.
- Added MON-001..010 consistency rules and a React monitoring dashboard with explicit missing-data states.

## Phase 26 — Signed Session Authentication & RBAC

- Added short-lived HMAC-SHA256 sessions, verified principals and enforced protected-route middleware.
- Added demo login, current-session and stateless logout APIs with secret-safe security events.
- Added React `sessionStorage` session handling, shared authenticated requests and 401/403 UI states.
- Added AUTH-001..AUTH-007 deployment consistency checks, tests and security documentation.
- Completed issued-at and 60–3600 second TTL validation, production-safe secret checks, logout auditing and AUTH-008 HTTP status semantics.
- Added the reusable anonymous demo AuthPanel and common login/me/logout client helpers without rendering or logging token values.

## Phase 23 — AI Literacy & Responsible AI

- Added versioned consent, transparency, model/dataset cards and Korean glossary.
- Added measured stage latency with average and p50/p95/p99 summaries.
- Added role-based education, quiz, issue reporting, Human-in-the-loop routing and responsible AI dashboard.
- Added twelve-risk registry, migration and backend/frontend tests.

형식은 Keep a Changelog를 따르며 버전은 Semantic Versioning을 사용한다.

## [0.4.0] - 2026-08-31

### Added
- LangGraph 기반 의료영상 업무지원 Agent와 deterministic dummy provider
- 7개 읽기 도구, 로컬 하이브리드 RAG, 근거 검증, 안전 필터
- 변경 도구 제안·사용자 확인 분리, 익명 trace와 피드백
- React Agent 패널과 6개 합성 평가 데이터셋

### Known limitations
- 외부 LLM, 의미 임베딩, vector DB, Redis/Celery, OpenTelemetry는 연결되지 않았다.
- Agent는 질병 진단 또는 치료 조언을 제공하지 않는다.

## [0.3.0] - 2026-08-30

### Added
- 단계별 안전 중단이 가능한 연구용 AI 파이프라인 실행 기록
- 전처리 비교, 합성 스트레스 시험, 재현성 manifest
- 기능 플래그, 알림, 데이터 계보, 이중 라벨 검수
- 결함·CAPA 연결 API와 MRI 어댑터 계약
- API 응답을 캐시하지 않는 제한형 PWA와 공개 포트폴리오 페이지

### Known limitations
- 실제 탐지, OCR, 랜드마크, 임상 성능 모델은 연결되지 않았다.
- Celery 기반 배치 추론, MLflow/DVC, 외부 메시징은 구성되지 않았다.

### Rollback
- 애플리케이션을 이전 `0.2.x` 이미지/커밋으로 전환하고 Alembic을 `0003_institution_integration`으로 내린다. 운영 데이터가 있다면 사전 백업과 복구 검증이 필수다.
