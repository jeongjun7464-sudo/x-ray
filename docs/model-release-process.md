# Model Release Gate

상태는 `REGISTERED → VALIDATING → APPROVAL_REQUIRED → APPROVED → DEPLOYED`이며 실패는 `REJECTED`, 교체 모델은 `RETIRED`가 된다. 모델 SHA-256, 학습/시험 데이터 버전, 필수 자동시험, 기존 모델 비교, 승인자·사유와 롤백 모델을 저장한다.

승인 전 배포는 409로 차단한다. 배포와 롤백은 ADMIN만 수행하며 모든 상태 변경은 감사 로그에 남는다. 이 게이트는 데모 워크플로이며 실제 규제 승인이나 임상 배포를 의미하지 않는다.
