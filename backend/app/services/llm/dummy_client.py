import hashlib,json,time
from .base import LLMResponse
class DummyLLMClient:
    def __init__(self,model_name="deterministic-agent-v1"):self.model_name=model_name
    def generate(self,messages,temperature,max_tokens,request_id):
        started=time.perf_counter();payload="\n".join(str(x.get("content","")) for x in messages);digest=hashlib.sha256(payload.encode()).hexdigest()[:8]
        docs=[]
        for line in payload.splitlines():
            if line.startswith("EVIDENCE|"):
                parts=line.split("|",5);docs.append({"document_id":parts[1],"version":parts[2],"section":parts[3],"chunk_id":parts[4]})
        content=json.dumps({"summary":f"승인된 자료를 바탕으로 업무 검토 항목을 정리했습니다. 참조 {digest}","recommended_review_steps":["구조화된 분석 결과와 영상 품질을 확인하세요.","필요하면 권한 있는 검토자에게 전달하세요."],"evidence":docs[:3],"limitations":["DEMO/DUMMY 언어모델 결과이며 의료적 확정 판단이 아닙니다."],"requires_human_review":True,"answer_type":"WORKFLOW_SUPPORT"},ensure_ascii=False,sort_keys=True)
        return LLMResponse(content,self.model_name,"dummy-v1","dummy",len(payload.split()),len(content.split()),round((time.perf_counter()-started)*1000,3),"stop",True,request_id)
