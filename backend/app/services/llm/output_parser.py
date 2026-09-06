import json
from .base import LLMError
FIELDS={"summary","recommended_review_steps","evidence","limitations","requires_human_review","answer_type"}
def parse_output(content):
    try:data=json.loads(content)
    except json.JSONDecodeError as exc:raise LLMError("LLM_INVALID_JSON","sLLM JSON을 해석할 수 없습니다.") from exc
    if not isinstance(data,dict) or not FIELDS.issubset(data):raise LLMError("LLM_SCHEMA_INVALID","sLLM 응답 스키마가 올바르지 않습니다.")
    if data["answer_type"]!="WORKFLOW_SUPPORT":raise LLMError("LLM_SCHEMA_INVALID","지원하지 않는 답변 유형입니다.")
    data["requires_human_review"]=True;return data
def verify_citations(data,documents):
    allowed={(d["document_id"],d["version"],d["section"],d["chunk_id"]) for d in documents};valid=[]
    for item in data.get("evidence",[]):
        key=tuple(item.get(x) for x in ("document_id","version","section","chunk_id"))
        if key in allowed:valid.append(item)
    data["evidence"]=valid;return data
