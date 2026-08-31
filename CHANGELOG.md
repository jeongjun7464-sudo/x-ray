# Changelog

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
