import re
FORBIDDEN=(r"확정 진단",r"치료해야",r"응급으로 확정",r"반드시 처방")
def sanitize_answer(data):
    flags=[];summary=str(data.get("summary",""))
    for pattern in FORBIDDEN:
        if re.search(pattern,summary,re.I):summary=re.sub(pattern,"의료진 확인 필요",summary,flags=re.I);flags.append("UNSUPPORTED_MEDICAL_CLAIM_REMOVED")
    data["summary"]=summary;data["requires_human_review"]=True;return data,flags
