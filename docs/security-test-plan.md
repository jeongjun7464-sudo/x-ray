# 보안 시험 계획

- 위조 확장자와 MIME/signature 불일치 차단
- 업로드 크기·배치 개수 제한
- ZIP `../` 및 절대 경로 차단, 중첩 ZIP 차단
- PHI 포함 합성 DICOM 경고와 금지 필드 거부
- 역할 없는 모델 승인·관리자 작업 거부(403)
- 요청 ID와 중요 변경 감사 로그 연결
- 감사 패키지 해시 변경 탐지
- 로그의 token, password, secret, authorization 값 마스킹

외부 악성코드 검사 adapter는 `NOT_CONFIGURED`이며 검사 완료로 기록하지 않는다. 관리자 재인증은 인터페이스 골격만 있고 IdP가 연결되지 않았다.
