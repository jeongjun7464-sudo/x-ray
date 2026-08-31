from __future__ import annotations
import math, re, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import func, select

from app.core.config import settings
from app.db.models import AuditEvent, Prediction

DOC_ROOT=Path(__file__).resolve().parents[3]
ALLOWED_DOCS=["README.md","docs/architecture.md","docs/api.md","docs/privacy-security.md","docs/validation-plan.md","docs/validation-summary.md","docs/traceability-matrix.md","docs/phase20-implementation-status.md","docs/phase21-implementation-status.md","docs/portfolio-description.md"]
INJECTION_PATTERNS=("ignore previous","ignore all instructions","system prompt","developer message","도구 제한을 무시","이전 지시를 무시","비밀번호를 출력")
PHI_PATTERNS=[(re.compile(r"\b\d{6}[- ]?[1-4]\d{6}\b"),"[MASKED_ID]"),(re.compile(r"(?i)(patientname|patientid|환자명|환자번호)\s*[:=]\s*\S+"),"[MASKED_PHI]"),(re.compile(r"\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b"),"[MASKED_PHONE]")]

class AgentState(TypedDict, total=False):
    request_id:str;user_id:str;user_role:str;user_query:str;intent:str;selected_agent:str
    retrieved_documents:list[dict];tool_calls:list[dict];tool_results:list[dict];generated_answer:str
    citations:list[dict];safety_flags:list[str];verification_result:dict;requires_human_confirmation:bool
    error:str|None;trace:list[dict]

def mask_sensitive(text:str)->tuple[str,bool]:
    masked=text;found=False
    for pattern,replacement in PHI_PATTERNS:
        masked,n=pattern.subn(replacement,masked);found|=n>0
    return masked,found

def _tokens(text:str)->list[str]: return re.findall(r"[가-힣A-Za-z0-9_-]{2,}",text.lower())

class HybridRetriever:
    def __init__(self):
        self.docs=[]
        for path in ALLOWED_DOCS:
            file=DOC_ROOT/path
            if not file.exists():continue
            text=file.read_text(encoding="utf-8",errors="replace")
            for index,chunk in enumerate(re.split(r"\n(?=#)",text)):
                title=(chunk.splitlines()[0].lstrip("# ") if chunk.splitlines() else path)[:160]
                self.docs.append({"document_id":f"{path}#{index}","document_type":"PROJECT_DOCUMENT","title":title,"version":"current","section":title,"path":path,"content":chunk[:5000],"approval_status":"PROJECT_CONTROLLED"})
    def search(self,query:str,limit=5)->list[dict]:
        q=_tokens(query);df=Counter(t for t in set(q) for d in self.docs if t in set(_tokens(d["content"])))
        ranked=[]
        for d in self.docs:
            words=_tokens(d["content"]);counts=Counter(words);bm=sum(counts[t]*math.log((len(self.docs)+1)/(df[t]+1)+1) for t in q)
            qset=set(q);dset=set(words);vector=len(qset&dset)/math.sqrt(max(1,len(qset))*max(1,len(dset)))
            ranked.append((bm,vector,d))
        bm_order={x[2]["document_id"]:i for i,x in enumerate(sorted(ranked,key=lambda x:x[0],reverse=True))};vec_order={x[2]["document_id"]:i for i,x in enumerate(sorted(ranked,key=lambda x:x[1],reverse=True))}
        fused=sorted(ranked,key=lambda x:1/(60+bm_order[x[2]["document_id"]])+1/(60+vec_order[x[2]["document_id"]]),reverse=True)
        return [{k:v for k,v in d.items() if k!="content"}|{"excerpt":d["content"][:600],"score_method":"BM25+token-vector RRF"} for bm,vec,d in fused[:limit] if bm>0 or vec>0]

def _prediction_data(p):
    return {"anonymous_analysis_id":p.id,"anatomical_region":p.anatomical_region,"confidence":p.confidence,"top_predictions":p.top_predictions,"laterality":p.laterality,"view_position":p.view_position,"review_required":p.review_required,"review_reasons":p.review_reasons,"model_version":p.model_version,"processing_time_ms":p.processing_time_ms}

class AgentTools:
    READ_ROLES={"USER","REVIEWER","ADMIN"}
    def __init__(self,db):self.db=db
    def call(self,name,args,role):
        if role not in self.READ_ROLES:raise PermissionError("ROLE_NOT_ALLOWED")
        allowed={"get_prediction":self.get_prediction,"list_predictions":self.list_predictions,"get_model_info":self.get_model_info,"get_system_health":self.get_system_health,"get_audit_summary":self.get_audit_summary,"get_test_results":self.get_test_results,"get_traceability_status":self.get_traceability_status}
        if name not in allowed:raise PermissionError("TOOL_NOT_ALLOWLISTED")
        return allowed[name](**args)
    def get_prediction(self,prediction_id):
        p=self.db.get(Prediction,prediction_id);return _prediction_data(p) if p else {"error":"NOT_FOUND"}
    def list_predictions(self,anatomical_region=None,confidence_max=None,review_status=None,model_version=None,limit=20):
        limit=max(1,min(int(limit),50));q=select(Prediction).order_by(Prediction.created_at.desc()).limit(limit)
        if anatomical_region:q=q.where(Prediction.anatomical_region==anatomical_region)
        if confidence_max is not None:q=q.where(Prediction.confidence<=float(confidence_max))
        if review_status:q=q.where(Prediction.review_required==(review_status=="PENDING"))
        if model_version:q=q.where(Prediction.model_version==model_version)
        return [_prediction_data(x) for x in self.db.scalars(q).all()]
    def get_model_info(self):return {"model_version":settings.model_version,"dummy_mode":settings.dummy_mode,"diagnostic_use":False}
    def get_system_health(self):return {"api":"UP","database":"UP","llm_provider":settings.llm_provider,"agent_mode":"deterministic" if settings.llm_provider=="dummy" else "configured-interface"}
    def get_audit_summary(self):return {"total":self.db.scalar(select(func.count()).select_from(AuditEvent)) or 0,"note":"식별정보와 원문 로그는 Agent에 제공하지 않습니다."}
    def get_test_results(self):
        p=DOC_ROOT/"docs/validation-summary.md";return {"document":"docs/validation-summary.md","content":p.read_text(encoding="utf-8")[:3000] if p.exists() else "UNAVAILABLE"}
    def get_traceability_status(self):
        p=DOC_ROOT/"docs/traceability-matrix.md";text=p.read_text(encoding="utf-8") if p.exists() else "";return {"status":"AVAILABLE" if text else "UNAVAILABLE","linked_rows":text.count("| URS-")+text.count("| REQ-")}

def _intent(query:str)->tuple[str,str,list[dict]]:
    q=query.lower()
    if any(x in q for x in ("테스트","시험","검증 보고")):return "TEST_RESULTS","Verification Agent",[{"name":"get_test_results","arguments":{}}]
    if any(x in q for x in ("추적성","요구사항","위험")):return "TRACEABILITY","Documentation Agent",[{"name":"get_traceability_status","arguments":{}}]
    if any(x in q for x in ("시스템 상태","장애","실패 원인")):return "SYSTEM_HEALTH","Security and Audit Agent",[{"name":"get_system_health","arguments":{}},{"name":"get_audit_summary","arguments":{}}]
    if any(x in q for x in ("모델","버전")):return "MODEL_INFO","Model Evaluation Agent",[{"name":"get_model_info","arguments":{}}]
    if any(x in q for x in ("검토","신뢰도","촬영 부위","분석 결과")):return "PREDICTION_SEARCH","Review Support Agent",[{"name":"list_predictions","arguments":natural_filter(query)}]
    return "DOCUMENT_SEARCH","Documentation Agent",[]

def natural_filter(query:str)->dict:
    result={"anatomical_region":None,"confidence_max":None,"review_status":None,"model_version":None,"limit":20}
    mapping={"무릎":"KNEE","흉부":"CHEST","손목":"HAND_WRIST","척추":"SPINE"}
    for word,region in mapping.items():
        if word in query:result["anatomical_region"]=region
    m=re.search(r"(\d{1,2})\s*%\s*(미만|이하)",query)
    if m:result["confidence_max"]=int(m.group(1))/100
    if "검토" in query and any(x in query for x in ("대기","미완료","끝나지")):result["review_status"]="PENDING"
    m=re.search(r"(?:모델|버전)\s*([A-Za-z0-9._-]+)",query)
    if m:result["model_version"]=m.group(1)[:64]
    return result

def run_agent(query:str,user_id:str,role:str,request_id:str,db)->dict:
    if len(query)>2000:raise ValueError("질문은 2,000자 이하여야 합니다.")
    masked,phi=mask_sensitive(query);flags=["PHI_MASKED"] if phi else []
    if any(x in masked.lower() for x in INJECTION_PATTERNS):flags.append("PROMPT_INJECTION_BLOCKED")
    retriever=HybridRetriever();tools=AgentTools(db);started=time.perf_counter()
    def node(name,fn):
        def wrapped(state):
            t=time.perf_counter();out=fn(state);trace=list(state.get("trace",[]));trace.append({"node":name,"duration_ms":round((time.perf_counter()-t)*1000,3)});out["trace"]=trace;return out
        return wrapped
    def classify(state):
        intent,agent,calls=_intent(state["user_query"]);return {"intent":intent,"selected_agent":agent,"tool_calls":calls}
    def retrieve(state):return {"retrieved_documents":retriever.search(state["user_query"],5)}
    def execute(state):
        if "PROMPT_INJECTION_BLOCKED" in state.get("safety_flags",[]):return {"tool_results":[],"error":"PROMPT_INJECTION_BLOCKED"}
        results=[]
        for call in state.get("tool_calls",[])[:5]:
            try:results.append({"tool":call["name"],"data":tools.call(call["name"],call["arguments"],state["user_role"])})
            except Exception as exc:results.append({"tool":call["name"],"error":type(exc).__name__})
        return {"tool_results":results}
    def generate(state):
        if state.get("error")=="PROMPT_INJECTION_BLOCKED":return {"generated_answer":"안전 정책을 변경하거나 내부 지시를 노출하도록 요구하는 요청은 처리할 수 없습니다."}
        evidence=state.get("tool_results",[]);docs=state.get("retrieved_documents",[])
        if not evidence and not docs:return {"generated_answer":"현재 등록된 문서와 시스템 데이터에서는 확인할 수 없습니다."}
        if evidence:return {"generated_answer":"요청과 관련된 시스템 데이터를 조회했습니다. 아래 도구 결과는 익명 분석 정보와 운영 상태만 포함하며 질병 또는 진단을 의미하지 않습니다.\n"+"\n".join(f"- {x['tool']}: {str(x.get('data',x.get('error')))[:900]}" for x in evidence)}
        return {"generated_answer":"등록된 프로젝트 문서에서 다음 근거를 찾았습니다.\n"+"\n".join(f"- {d['title']}: {d['excerpt'][:280]}" for d in docs[:3])}
    def verify(state):
        grounded=bool(state.get("tool_results") or state.get("retrieved_documents"));return {"verification_result":{"grounded":grounded,"unsupported_claims":0 if grounded else 1},"citations":[{"document_id":d["document_id"],"title":d["title"],"version":d["version"],"location":d["section"],"path":d["path"]} for d in state.get("retrieved_documents",[])[:5]]}
    graph=StateGraph(AgentState);graph.add_node("classify",node("classify",classify));graph.add_node("retrieve",node("retrieve",retrieve));graph.add_node("tools",node("tools",execute));graph.add_node("generate",node("generate",generate));graph.add_node("verify",node("verify",verify));graph.add_edge(START,"classify");graph.add_edge("classify","retrieve");graph.add_edge("retrieve","tools");graph.add_edge("tools","generate");graph.add_edge("generate","verify");graph.add_edge("verify",END)
    initial:AgentState={"request_id":request_id,"user_id":user_id,"user_role":role,"user_query":masked,"safety_flags":flags,"trace":[],"tool_calls":[],"tool_results":[],"retrieved_documents":[]}
    result=graph.compile().invoke(initial,{"recursion_limit":12});answer,_=mask_sensitive(result["generated_answer"]);result["generated_answer"]=answer;result["total_duration_ms"]=round((time.perf_counter()-started)*1000,3);result["provider"]="dummy";result["model"]="deterministic-agent-v1";result["confidence_level"]="HIGH" if result.get("verification_result",{}).get("grounded") else "LOW";result["requires_human_confirmation"]=False;return result
