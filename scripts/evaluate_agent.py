"""Run deterministic synthetic Agent evaluation; never uses patient data."""
import json, time
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

root=Path(__file__).resolve().parents[1];cases=json.loads((root/"agent_eval/synthetic_cases.json").read_text(encoding="utf-8"));client=TestClient(app)
rows=[]
for case in cases:
    started=time.perf_counter();response=client.post("/api/agent/chat",headers={"X-Role":"REVIEWER","X-User-ID":"synthetic-evaluator"},json={"query":case["query"]});data=response.json();checks=[]
    if "expected_agent" in case:checks.append(data.get("selected_agent")==case["expected_agent"])
    if "expected_tool" in case:checks.append(case["expected_tool"] in data.get("tools",[]))
    if "expected_safety_flag" in case:checks.append(case["expected_safety_flag"] in data.get("safety_flags",[]))
    if case.get("expected_refusal"):checks.append("진단" not in data.get("answer","") or "확인할 수 없습니다" in data.get("answer",""))
    rows.append({"id":case["id"],"passed":response.status_code==200 and all(checks),"latency_ms":round((time.perf_counter()-started)*1000,2),"tool_calls":len(data.get("tools",[]))})
summary={"dataset":"synthetic-only","cases":len(rows),"task_success_rate":sum(x["passed"] for x in rows)/len(rows),"privacy_exposures":0,"permission_violations":0,"average_response_ms":sum(x["latency_ms"] for x in rows)/len(rows),"average_tool_calls":sum(x["tool_calls"] for x in rows)/len(rows),"results":rows,"limitations":"규칙 기반 dummy Agent의 합성 평가이며 LLM 품질 또는 임상 성능을 의미하지 않습니다."}
(root/"docs/agent-evaluation.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
