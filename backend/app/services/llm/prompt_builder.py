import json
PROMPT_VERSION="grounded-workflow-v1"
SYSTEM="""당신은 의료영상 업무지원 도구다. 질병, 치료, 응급 여부를 확정하지 않는다. 제공된 구조화 결과와 승인 근거만 사용하고 JSON으로 답한다. 근거가 없으면 답하지 않는다. 개인정보나 원본 영상은 다루지 않는다."""
def build_grounded_prompt(role,question,structured_result,documents,tool_results):
    evidence="\n".join(f'EVIDENCE|{d["document_id"]}|{d["version"]}|{d["section"]}|{d["chunk_id"]}|{d["content"]}' for d in documents)
    content=f"ROLE={role}\nQUESTION={question}\nSTRUCTURED_RESULT={json.dumps(structured_result or {},ensure_ascii=False)}\n{evidence}\nTOOLS={json.dumps(tool_results,ensure_ascii=False)}\nOUTPUT_SCHEMA=summary,recommended_review_steps,evidence,limitations,requires_human_review,answer_type"
    return [{"role":"system","content":SYSTEM},{"role":"user","content":content}]
