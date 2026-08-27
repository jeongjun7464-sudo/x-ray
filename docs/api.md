# API

OpenAPI UI는 `/docs`, 스키마는 `/openapi.json`에서 제공한다.

- `GET /api/health`, `/api/model/info`, `/api/classes`
- `POST /api/images/validate`: 영상 유효성만 확인
- `POST /api/predictions`: 분석 및 결과 저장
- `GET /api/predictions`, `GET /api/predictions/{id}`
- `PATCH /api/predictions/{id}/review`: `{ "corrected_region": "CHEST", "comment": "..." }`
- `GET /api/statistics/summary`, `/api/statistics/confusion-matrix`

파일 오류는 `{ "error": { "code": "INVALID_FILE", "message": "..." } }` 형식을 사용한다. 프레임워크 입력 검증 오류는 FastAPI 표준 422 형식이다.
