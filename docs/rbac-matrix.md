# RBAC 매트릭스

## QMS 권한

QMS는 개발 모드에서도 실제 서명 Principal을 요구한다(미인증 401, 권한 부족 403). QA_RA는 작성·독립 검토·패키지 생성, ML_ENGINEER는 허용된 기술 요구사항·변경·초안 작성, ADMIN은 조회·게이트 적용 배포, RADIOLOGIST/TECHNICIAN/ADJUDICATOR는 QMS 조회가 가능하다. 전자승인은 재인증 미설정으로 차단된다. 세부 임상 요구사항 리뷰 기능은 아직 추가 작업이다.

| 역할 | 허용 작업 |
|---|---|
| USER | 공개·일반 조회, 본인 세션 정보 확인 |
| TECHNICIAN | Study 등록, 분석 요청 |
| REVIEWER / RADIOLOGIST | Study 결과 검토, 우선순위 수정, 검증된 Grad-CAM 조회 |
| ML_ENGINEER | 모델 등록, 검증 요청 |
| QA_RA | 모델 시험·승인, CAPA 관리 |
| ADMIN | 우선순위 규칙, 배포·롤백, 사용자·연동 설정 |

서명된 세션의 `Principal.role`이 권한 판단의 기준이다. 개발 호환 모드에서만 `X-Role`을 허용하며 `AUTH_ENFORCED=true`에서는 해당 헤더를 신뢰하지 않는다. 인증 실패는 401, 인증 후 권한 부족은 403이고 중요 변경과 실패는 토큰 원문 없이 감사·보안 이벤트로 기록한다. 조직 IdP/OIDC, MFA와 중앙 세션 폐기는 아직 `NOT_CONFIGURED`이다.
