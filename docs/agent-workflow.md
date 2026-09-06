# LangGraph Agent Workflow

`validate_input → classify_intent → check_permission → build_search_query → hybrid_retrieve → filter_evidence → select_allowed_tools → execute_tools → build_grounded_prompt → call_sllm → parse_response → verify_citations → safety_check → save_trace` 순서다. 상태는 COMPLETED, NO_EVIDENCE, PERMISSION_DENIED, SAFETY_BLOCKED, LLM_UNAVAILABLE, RETRIEVAL_UNAVAILABLE, DEGRADED를 구분한다. 변경은 기존 proposal/confirm API만 사용한다.
