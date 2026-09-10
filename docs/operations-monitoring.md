# 운영 모니터링

Phase 28 배포는 최신 Phase 27 Release Gate를 사용하며 CRITICAL drift는 검증 정답 없이 성능 저하라고 단정하지 않고 배포·Canary 차단으로 처리한다.

Phase 27 대시보드는 `GET /api/v1/monitoring/dashboard`에서 최신 스냅샷, 분포, 미해결 경고, 배포 차단과 CAPA 후보를 제공한다. 값이 없는 비율은 0으로 대체하지 않으며 측정 기간과 표본 수를 함께 표시한다. 스냅샷 생성·조회와 드리프트 상세 정책은 [Phase 27 문서](phase27-model-monitoring-drift.md)를 따른다.

대시보드는 총 분석, 성공률, 평균/P95 처리시간, 품질 REJECT, OOD, 의료진 검토, 검토 소요시간, API 오류율, 모델 사용량, 최근 오류와 PACS/DB/모델/큐 상태를 제공한다.

프로세스 내 API 오류 집계는 재시작 시 초기화되는 데모 지표다. 자료가 없는 지표는 `null`/`NOT_MEASURED`이며 임의 값을 생성하지 않는다. 운영 환경에서는 영속 메트릭 저장소와 알림 연동이 추가로 필요하다.
