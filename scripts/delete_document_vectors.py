"""Disable document versions through the audited API; physical deletion is intentionally unsupported."""
import argparse,json,urllib.request
p=argparse.ArgumentParser();p.add_argument("document_id");p.add_argument("version");p.add_argument("--reason",required=True);p.add_argument("--api",default="http://localhost:8000")
if __name__=="__main__":
    a=p.parse_args();url=f"{a.api}/api/v1/admin/knowledge/documents/{a.document_id}/versions/{a.version}";request=urllib.request.Request(url,json.dumps({"reason":a.reason}).encode(),{"Content-Type":"application/json","X-Role":"ADMIN"},method="DELETE")
    with urllib.request.urlopen(request) as response:print(response.read().decode())
