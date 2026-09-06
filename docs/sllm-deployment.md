# sLLM 및 Qdrant 배포

`docker compose up --build`는 PostgreSQL, API, React와 Qdrant를 실행한다. GPU가 있는 선택 환경에서만 `docker compose --profile gpu up vllm`을 사용한다. 모델은 `VLLM_MODEL_PATH`, API는 `LLM_BASE_URL`, provider는 `LLM_PROVIDER=vllm`로 설정한다. 모델 파일과 API 키는 저장소에 넣지 않는다. Qdrant가 준비되지 않아도 API는 시작하며 Agent가 로컬 검색 fallback을 표시한다.
