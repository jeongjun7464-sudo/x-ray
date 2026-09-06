import json,urllib.error,urllib.request
from app.core.config import settings
class QdrantStore:
    def __init__(self):self.url=settings.qdrant_url.rstrip("/");self.collection=settings.qdrant_collection;self.key=settings.qdrant_api_key
    def _call(self,path,method="GET",body=None,timeout=2):
        headers={"Content-Type":"application/json"}
        if self.key:headers["api-key"]=self.key
        req=urllib.request.Request(self.url+path,json.dumps(body).encode() if body is not None else None,headers,method=method)
        with urllib.request.urlopen(req,timeout=timeout) as response:return json.loads(response.read())
    def status(self):
        try:data=self._call(f"/collections/{self.collection}");result=data.get("result",{});return {"connection_status":"CONNECTED","collection_status":result.get("status","UNKNOWN"),"vector_count":result.get("points_count",0)}
        except Exception:return {"connection_status":"NOT_CONFIGURED_OR_UNAVAILABLE","collection_status":"UNAVAILABLE","vector_count":None}
    def ensure_collection(self):
        if self.status()["connection_status"]=="CONNECTED":return
        self._call(f"/collections/{self.collection}","PUT",{"vectors":{"size":settings.qdrant_vector_size,"distance":"Cosine"}},5)
    def upsert(self,points):self.ensure_collection();return self._call(f"/collections/{self.collection}/points?wait=true","PUT",{"points":points},10)
    def search(self,vector,filters,limit):
        must=[{"key":k,"match":{"value":v}} for k,v in filters.items() if v is not None]
        data=self._call(f"/collections/{self.collection}/points/search","POST",{"vector":vector,"limit":limit,"with_payload":True,"filter":{"must":must}},5)
        return [x.get("payload",{})|{"vector_score":x.get("score",0),"qdrant_point_id":str(x.get("id"))} for x in data.get("result",[])]
