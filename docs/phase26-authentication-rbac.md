# Phase 26 — 서명 세션 인증과 RBAC

## 구현 범위

`backend/app/core/auth.py`는 URL-safe payload와 HMAC-SHA256 서명으로 구성된 짧은 세션 토큰을 발급·검증한다. 검증 결과는 `Principal(subject, role, expires_at, authentication_method)`이며 미들웨어가 요청 범위에 설정한다. 역할 검사는 클라이언트가 주장한 헤더보다 검증된 Principal을 우선한다.

데모 API는 `POST /api/auth/demo-token`, `GET /api/auth/me`, `POST /api/auth/logout`이다. 로그아웃은 클라이언트 토큰 삭제만 수행하며 서버 폐기 목록은 `NOT_CONFIGURED`로 명시한다. 이는 임상 운영 인증을 의미하지 않는다.

## 모드

| 설정 | 개발 기본값 | 보안·운영 권장값 |
|---|---:|---:|
| `AUTH_ENFORCED` | `false` | `true` |
| `AUTH_ALLOW_LEGACY_HEADERS` | `true` | `false` |
| `AUTH_DEMO_TOKENS_ENABLED` | `true` | `false` |
| `AUTH_SESSION_TTL_SECONDS` | `900` | 최대 `3600` |
| `AUTH_SESSION_SECRET` | 비어 있음 | 외부 비밀 저장소에서 32자 이상 주입 |

보안 모드에서 비밀값이 짧거나 없으면 시작을 거부한다. 공개 경로는 health, 모델 정보, 클래스, 데모 토큰(개발 전용), API 문서로 제한한다.

## 실패 처리와 위협 경계

- 누락·만료·변조·잘못된 역할 토큰: 구체적인 검증 정보를 노출하지 않는 401
- 인증된 사용자 권한 부족: 403
- `AUTH_ENFORCED=true`에서 `X-Role`/`X-User-ID` 위조: 권한 근거로 사용하지 않음
- 토큰 원문, Authorization 헤더, 서명키: 로그 및 SecurityEvent 저장 금지
- 조직 IdP, MFA, 중앙 로그아웃·폐기, 키 순환, 분산 세션: 향후 외부 연동 영역

## 로컬 실행

`.env.example`을 참고해 개발 전용 비밀값을 환경변수로 주입한다. 운영 비밀값을 `.env`, Git, 테스트 fixture 또는 문서에 커밋하지 않는다. 보안 모드 전환 전 AUTH-001부터 AUTH-007까지 검증하고 실패 시 모델 승인·배포를 차단한다.
