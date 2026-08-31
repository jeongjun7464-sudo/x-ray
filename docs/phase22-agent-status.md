# Phase 22 의료영상 AI Agent 및 RAG 구현 현황

## 실제 구현

| 기능 | 상태 | 근거 |
|---|---|---|
| LangGraph 상태 실행 | 구현 | `StateGraph`의 classify→retrieve→tools→generate→verify 노드 실제 호출 |
| deterministic dummy Agent | 구현 | API 키 없이 동일 규칙·데이터에서 재현 가능 |
| 읽기 도구 | 구현 | prediction 목록/상세, 모델, 시스템 상태, 감사 요약, 시험 결과, 추적성 총 7개 |
| 도구 allowlist/RBAC | 구현 | 임의 도구와 임의 SQL 차단, Pydantic 입력 제한 |
| 변경 도구 확인 | 구현 | 제안 저장 후 별도 confirm API에서만 service layer 실행 |
| 프로젝트 문서 RAG | 구현 | 허용된 저장소 문서만 청킹·검색 |
| 하이브리드 검색 | 부분 구현 | BM25 유사 점수 + token-vector cosine + RRF. pgvector/Qdrant와 sentence-transformers는 미연결 |
| 근거 답변 | 구현 | 문서 ID·버전·섹션·경로 및 사용 시스템 도구 표시 |
| 개인정보 보호 | 구현 | PatientID/PatientName/전화/주민번호 패턴 마스킹, 원본 영상·전체 태그 미전달 |
| Prompt injection 방어 | 구현 | 알려진 공격 패턴 차단, 검색 문서는 데이터로만 처리 |
| 실행 trace | 구현 | 노드 시간, 검색 수, 도구 수, 모델, 안전 결과 저장 |
| Agent UI/피드백 | 구현 | 질문·추천 질문·단계·도구·근거·피드백 표시 |
| 합성 평가 | 구현 | 6개 합성 사례와 실제 측정 JSON |

## 부분 또는 미구현

- OpenAI-compatible, local-vLLM, Ollama는 환경 설정 필드만 있고 실제 네트워크 호출 어댑터는 미구현이다.
- Qwen/Llama, Kiwi, sentence-transformers, ONNX embedding, pgvector/Qdrant, Redis/Celery, OpenTelemetry는 설치·연결하지 않았으며 실제 사용 기술로 표시하지 않는다.
- 현재 vector 점수는 로컬 token-vector 방식이다. 의미 임베딩 품질을 주장하지 않는다.
- 실제 토큰과 비용은 dummy 모드에서 0이며 외부 제공자 비용 계산은 미구현이다.
- Agent가 서비스 재시작, 삭제, 모델 배포·롤백을 실행하는 도구는 제공하지 않는다.
- 합성 평가 성공률은 규칙 기반 dummy Agent 회귀시험 결과이며 LLM 품질이나 임상 성능을 의미하지 않는다.

Agent는 촬영 부위 분류 결과와 시스템 상태를 설명할 뿐 질병·병변·치료를 추론하지 않는다.
