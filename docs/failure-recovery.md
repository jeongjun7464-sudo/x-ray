# 장애 및 복구

작업 상태는 QUEUED, PROCESSING, SUCCEEDED, RETRY_PENDING, QUARANTINED, FAILED, MANUAL_REVIEW를 지원한다. Idempotency-Key로 중복 생성을 차단하고 최대 5회의 제한 재시도와 60초 상한 지수 백오프를 적용한다. 모델 서버 장애는 의료진 검토 대상으로 표시한다. 관리자만 수동 재처리할 수 있고 롤백 완료 후 성공으로 전환할 수 있다. 현재 큐는 로컬 상태 머신이며 외부 작업 큐는 연결되지 않았다.
