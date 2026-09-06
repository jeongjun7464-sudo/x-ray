# sLLM 업무지원 아키텍처

영상 파이프라인은 구조화 결과만 Agent에 전달한다. LangGraph는 입력·권한·검색·도구·grounded prompt·sLLM·JSON/근거/안전 검증·trace 저장을 순서대로 실행한다. sLLM은 픽셀을 직접 보지 않으며 질병·치료·응급 여부를 확정하지 않는다. 기본 provider는 재현 가능한 `dummy`; `vllm`과 `openai-compatible`은 외부 endpoint가 있을 때만 사용한다. 장애가 나도 영상 분석은 유지하고 Agent만 `LLM_UNAVAILABLE` 또는 `DEGRADED`가 된다.
