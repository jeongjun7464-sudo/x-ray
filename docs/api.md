# API

## Phase 30 QMS API

`/api/v1/qms` 아래 requirements, risks/risk-matrix, traceability-links/traceability/gaps/orphans/traceability-export, change-requests, capas, documents, approvals, audit-chain, audit-packages, consistency/validate, dashboard, tests, defects를 제공한다. 실제 method/path와 strict 입력 스키마는 FastAPI `/openapi.json`에 등록되어 있다. 중요 승인 응답은 REAUTHENTICATION_NOT_CONFIGURED이며 승인 성공으로 처리하면 안 된다.

OpenAPI UI는 `/docs`, 스키마는 `/openapi.json`에서 제공한다.

## Phase 28 ModelOps

- `POST/GET /api/v1/model-releases`, `GET /api/v1/model-releases/{id}`
- `POST /api/v1/model-releases/{id}/artifact|validate|request-approval|approve|reject|deploy`
- `POST/GET/PATCH /api/v1/validation-policies`
- `GET /api/v1/model-validation-runs`, `GET /api/v1/model-validation-runs/{id}`, `POST .../cancel|retest`, `GET .../report`
- `POST /api/v1/deployments/{id}/rollback`

변경 API는 서명 세션 Principal과 역할 분리를 사용한다. 개발 호환 모드에서만 `X-Role`/`X-Actor`를 허용한다. 모델 검증은 `Idempotency-Key`가 필수이며 운영 배포는 재인증 연동 전까지 차단된다.

- `GET /api/health`, `/api/model/info`, `/api/classes`
- `POST /api/images/validate`: 영상 유효성만 확인
- `POST /api/predictions`: 분석 및 결과 저장
- `GET /api/predictions`, `GET /api/predictions/{id}`
- `PATCH /api/predictions/{id}/review`: `{ "corrected_region": "CHEST", "comment": "..." }`
- `GET /api/statistics/summary`, `/api/statistics/confusion-matrix`

파일 오류는 `{ "error": { "code": "INVALID_FILE", "message": "..." } }` 형식을 사용한다. 프레임워크 입력 검증 오류는 FastAPI 표준 422 형식이다.
