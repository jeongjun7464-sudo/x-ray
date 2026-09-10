import hashlib
from pathlib import PurePath

ALLOWED={"pt","pth","onnx","safetensors"}
MAGIC={"onnx":None,"safetensors":None,"pt":b"PK","pth":b"PK"}

def validate_artifact(filename:str,data:bytes,declared_sha256:str|None=None,max_bytes:int=50*1024*1024)->dict:
    safe=PurePath(filename).name
    if safe!=filename or ".." in filename: return {"status":"FAILED","reason_codes":["PATH_TRAVERSAL"]}
    ext=safe.rsplit(".",1)[-1].lower() if "." in safe else ""
    if ext not in ALLOWED:return {"status":"FAILED","reason_codes":["FORMAT_NOT_ALLOWED"]}
    if not data:return {"status":"FAILED","reason_codes":["EMPTY_ARTIFACT"]}
    if len(data)>max_bytes:return {"status":"FAILED","reason_codes":["SIZE_LIMIT_EXCEEDED"]}
    digest=hashlib.sha256(data).hexdigest();reasons=[]
    if declared_sha256 and digest!=declared_sha256.lower():reasons.append("CHECKPOINT_HASH_MISMATCH")
    if ext in {"pt","pth"}:
        reasons.append("PICKLE_EXECUTION_RISK")
        signature="WARNING"
    elif ext=="onnx":signature="VERIFIED" if data[:1]==b"\x08" else "NOT_VERIFIABLE"
    else:
        header_length=int.from_bytes(data[:8],"little") if len(data)>=8 else 0
        signature="VERIFIED" if 0<header_length<=len(data)-8 and data[8:9]==b"{" else "NOT_VERIFIABLE"
    # A byte prefix is not structural, tensor or malware verification.
    if signature=="VERIFIED":signature="PREFIX_ONLY"
    status="FAILED" if "CHECKPOINT_HASH_MISMATCH" in reasons else "MANUAL_REVIEW_REQUIRED" if reasons else "NOT_VERIFIABLE"
    return {"status":status,"sha256":digest,"size_bytes":len(data),"format":ext.upper(),"signature_status":signature,"malware_scan_status":"NOT_CONFIGURED","reason_codes":reasons,"safe_to_load":False}
