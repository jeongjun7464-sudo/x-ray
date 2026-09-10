# Model Release Gate

Phase 28은 아티팩트·데이터 계보·승인 정책·독립 QA/RA 승인·Release Gate·rollback 대상을 모두 요구하며 승인만으로 자동 배포하지 않는다.

승인 상태만으로 배포할 수 없다. `POST /api/v1/releases/{release_id}/monitoring-gate`가 최신 모니터링 증적, CRITICAL 드리프트, 모델 해시, 검증 데이터셋 버전과 최근 정합성 실패를 확인한다. `blocked=true`이면 릴리스는 중단되며 결과가 자동 승인이나 자동 배포를 수행하지 않는다.

상태는 `REGISTERED → VALIDATING → APPROVAL_REQUIRED → APPROVED → DEPLOYED`이며 실패는 `REJECTED`, 교체 모델은 `RETIRED`가 된다. 모델 SHA-256, 학습/시험 데이터 버전, 필수 자동시험, 기존 모델 비교, 승인자·사유와 롤백 모델을 저장한다.

승인 전 배포는 409로 차단한다. 배포와 롤백은 ADMIN만 수행하며 모든 상태 변경은 감사 로그에 남는다. 이 게이트는 데모 워크플로이며 실제 규제 승인이나 임상 배포를 의미하지 않는다.
