from __future__ import annotations
import time
from typing import TypedDict
from langgraph.graph import END,START,StateGraph
from app.core.config import settings
from app.services.llm import LLMError,create_llm_client
from app.services.llm.output_parser import parse_output,verify_citations
from app.services.llm.prompt_builder import PROMPT_VERSION,build_grounded_prompt
from app.services.llm.safety import sanitize_answer
from app.services.medical_agent import AgentTools,INJECTION_PATTERNS,mask_sensitive,_intent
from app.services.retrieval import HybridRetriever
class GroundedState(TypedDict,total=False):
    request_id:str;role:str;institution_id:str;question:str;analysis_id:str|None;structured_xray_result:dict;intent:str;search_query:str;retrieved_documents:list;selected_documents:list;tool_calls:list;tool_results:list;llm_response:dict;answer:dict;citations:list;unsupported_claims:list;safety_flags:list;response_status:str;retrieval_mode:str;trace:list;error:str|None
def run_grounded_agent(question,analysis_id,role,institution_id,request_id,db):
    started=time.perf_counter();retriever=HybridRetriever();tools=AgentTools(db)
    def timed(name,fn):
        def call(s):
            t=time.perf_counter();out=fn(s);out["trace"]=list(s.get("trace",[]))+[{"node":name,"latency_ms":round((time.perf_counter()-t)*1000,3)}];return out
        return call
    def validate(s):
        masked,phi=mask_sensitive(s["question"]);flags=["PHI_MASKED"] if phi else []
        if any(x in masked.lower() for x in INJECTION_PATTERNS):flags.append("PROMPT_INJECTION_BLOCKED");return {"question":masked,"safety_flags":flags,"response_status":"SAFETY_BLOCKED"}
        return {"question":masked,"safety_flags":flags}
    def classify(s):intent,_,calls=_intent(s["question"]);return {"intent":intent,"tool_calls":calls,"search_query":s["question"]}
    def permission(s):return {"response_status":"PERMISSION_DENIED"} if s["role"] not in {"USER","REVIEWER","RADIOLOGIST","ML_ENGINEER","QA_RA","ADMIN"} else {}
    def retrieve(s):
        if s.get("response_status") in {"SAFETY_BLOCKED","PERMISSION_DENIED"}:return {"retrieved_documents":[],"selected_documents":[]}
        result=retriever.search(s["search_query"],s["role"],s["institution_id"]);return {"retrieved_documents":result["results"],"selected_documents":result["results"],"retrieval_mode":result["mode"],"response_status":"NO_EVIDENCE" if not result["results"] else ("DEGRADED" if result["mode"]=="LOCAL_FALLBACK" else "COMPLETED")}
    def execute(s):
        results=[]
        for call in s.get("tool_calls",[])[:5]:
            try:results.append({"tool":call["name"],"data":tools.call(call["name"],call["arguments"],"REVIEWER" if s["role"]=="RADIOLOGIST" else s["role"])})
            except Exception as exc:results.append({"tool":call["name"],"error":type(exc).__name__})
        structured={};
        if analysis_id:=s.get("analysis_id"):structured=tools.get_prediction(analysis_id)
        return {"tool_results":results,"structured_xray_result":structured}
    def llm(s):
        if s.get("response_status") in {"NO_EVIDENCE","SAFETY_BLOCKED","PERMISSION_DENIED"}:return {}
        messages=build_grounded_prompt(s["role"],s["question"],s.get("structured_xray_result",{}),s["selected_documents"],s.get("tool_results",[]))
        try:return {"llm_response":create_llm_client().generate(messages,settings.llm_temperature,settings.llm_max_tokens,s["request_id"]).dict()}
        except LLMError as exc:return {"response_status":"LLM_UNAVAILABLE","error":exc.code}
    def parse(s):
        if not s.get("llm_response"):return {}
        try:data=parse_output(s["llm_response"]["content"]);data=verify_citations(data,s["selected_documents"]);data,flags=sanitize_answer(data);return {"answer":data,"citations":data["evidence"],"safety_flags":list(s.get("safety_flags",[]))+flags}
        except LLMError as exc:return {"response_status":"LLM_UNAVAILABLE","error":exc.code}
    def finish(s):
        status=s.get("response_status","COMPLETED")
        if status=="DEGRADED" and not s.get("answer"):status="LLM_UNAVAILABLE"
        return {"response_status":status}
    graph=StateGraph(GroundedState)
    for name,fn in (("validate_input",validate),("classify_intent",classify),("check_permission",permission),("build_search_query",lambda s:{}),("hybrid_retrieve",retrieve),("filter_evidence",lambda s:{}),("select_allowed_tools",lambda s:{}),("execute_tools",execute),("build_grounded_prompt",lambda s:{}),("call_sllm",llm),("parse_response",parse),("verify_citations",lambda s:{}),("safety_check",lambda s:{}),("save_trace",finish)):graph.add_node(name,timed(name,fn))
    names=["validate_input","classify_intent","check_permission","build_search_query","hybrid_retrieve","filter_evidence","select_allowed_tools","execute_tools","build_grounded_prompt","call_sllm","parse_response","verify_citations","safety_check","save_trace"]
    graph.add_edge(START,names[0]);[graph.add_edge(a,b) for a,b in zip(names,names[1:])];graph.add_edge(names[-1],END)
    result=graph.compile().invoke({"request_id":request_id,"role":role,"institution_id":institution_id,"question":question,"analysis_id":analysis_id,"trace":[],"safety_flags":[],"tool_calls":[],"retrieved_documents":[],"selected_documents":[]});result["total_latency_ms"]=round((time.perf_counter()-started)*1000,3);result["prompt_template_version"]=PROMPT_VERSION;return result
