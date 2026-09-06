import hashlib

DISCLAIMER="연구·교육용 보조 결과이며 의료진 확인 전에는 확정되지 않습니다."

def comparison_compatibility(prior:dict,current:dict)->dict:
    fields=("view_position","resolution","equipment")
    mismatches=[field for field in fields if prior.get(field) and current.get(field) and prior[field]!=current[field]]
    missing=[field for field in fields if not prior.get(field) or not current.get(field)]
    status="LIMITED" if mismatches or missing else "COMPARABLE"
    return {"status":status,"mismatches":mismatches,"missing":missing,"confidence_limit":("촬영 방향·해상도·장비 조건 차이로 변화 비교 신뢰도가 제한됩니다." if status=="LIMITED" else None)}

def split_for_patient(patient_hash:str)->str:
    bucket=int(hashlib.sha256(patient_hash.encode()).hexdigest()[:8],16)%100
    return "train" if bucket<70 else "validation" if bucket<85 else "test"

def build_manifest(items:list[dict])->tuple[list[dict],int]:
    seen=set(); manifest=[]; duplicates=0
    for item in items:
        image_hash=str(item.get("anonymous_hash","")).lower(); patient_hash=str(item.get("patient_hash","")).lower()
        if len(image_hash)!=64 or len(patient_hash)!=64: raise ValueError("익명 SHA-256 image/patient hash가 필요합니다.")
        if image_hash in seen: duplicates+=1; continue
        seen.add(image_hash); manifest.append({"anonymous_hash":image_hash,"patient_hash":patient_hash,"split":split_for_patient(patient_hash),"region":item.get("region","UNKNOWN"),"findings":sorted(set(item.get("findings",[]))),"label_status":item.get("label_status","PENDING")})
    return manifest,duplicates

def failure_metrics(rows:list[dict])->dict:
    approved=[x for x in rows if x.get("ground_truth")]
    if not approved:return {"status":"NOT_MEASURED","reason":"승인된 실제 검증 정답 데이터가 없습니다.","confusion_matrix":None,"false_positive":None,"false_negative":None,"subgroups":None}
    labels=sorted({x["ground_truth"] for x in approved}|{x.get("prediction","UNKNOWN") for x in approved})
    matrix={truth:{pred:0 for pred in labels} for truth in labels}
    for x in approved:matrix[x["ground_truth"]][x.get("prediction","UNKNOWN")]+=1
    return {"status":"MEASURED","sample_size":len(approved),"confusion_matrix":matrix,"false_positive":sum(x.get("prediction")!=x["ground_truth"] for x in approved),"false_negative":"소견별 승인 정답 필요","subgroups":"기관·장비별 최소 표본 기준 적용 필요"}
