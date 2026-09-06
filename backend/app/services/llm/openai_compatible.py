import json,time,urllib.error,urllib.request
from .base import LLMError,LLMResponse
class OpenAICompatibleClient:
    def __init__(self,base_url,model,api_key="",timeout=60,retries=1,provider="openai-compatible"):
        self.base_url=base_url.rstrip("/");self.model=model;self.api_key=api_key;self.timeout=timeout;self.retries=max(0,min(retries,2));self.provider=provider;self.last_latency_ms=None
    def generate(self,messages,temperature,max_tokens,request_id):
        body=json.dumps({"model":self.model,"messages":messages,"temperature":temperature,"max_tokens":max_tokens,"response_format":{"type":"json_object"}}).encode();headers={"Content-Type":"application/json","X-Request-ID":request_id}
        if self.api_key:headers["Authorization"]="Bearer "+self.api_key
        started=time.perf_counter()
        for attempt in range(self.retries+1):
            try:
                with urllib.request.urlopen(urllib.request.Request(self.base_url+"/chat/completions",body,headers),timeout=self.timeout) as response:data=json.loads(response.read())
                choice=data["choices"][0];usage=data.get("usage",{});latency=round((time.perf_counter()-started)*1000,3);self.last_latency_ms=latency
                return LLMResponse(choice["message"]["content"],self.model,str(data.get("model",self.model)),self.provider,int(usage.get("prompt_tokens",0)),int(usage.get("completion_tokens",0)),latency,str(choice.get("finish_reason","unknown")),False,request_id)
            except (TimeoutError,urllib.error.URLError) as exc:
                if attempt==self.retries:raise LLMError("LLM_TIMEOUT" if isinstance(getattr(exc,"reason",None),TimeoutError) or isinstance(exc,TimeoutError) else "LLM_CONNECTION_ERROR","sLLM에 연결할 수 없습니다.") from exc
            except (KeyError,ValueError,json.JSONDecodeError) as exc:raise LLMError("LLM_INVALID_RESPONSE","sLLM 응답 형식이 올바르지 않습니다.") from exc
