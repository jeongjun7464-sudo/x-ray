ALLOWED_CLINICAL_FIELDS={"anonymous_subject_id","age_group","sex","symptom_codes","imaging_purpose","exam_location"}
FORBIDDEN_CLINICAL_FIELDS={"name","patient_name","resident_registration_number","ssn","phone","telephone","address"}
DEFAULT_THRESHOLDS={"high_priority_finding_probability":0.8,"capa_repeat_count":3}

def validate_clinical_context(value:dict|None)->dict:
    value=value or {}; keys={str(x).lower() for x in value}
    forbidden=keys&FORBIDDEN_CLINICAL_FIELDS
    if forbidden:raise ValueError("금지된 개인정보 필드: "+", ".join(sorted(forbidden)))
    unknown=keys-ALLOWED_CLINICAL_FIELDS
    if unknown:raise ValueError("허용되지 않은 임상정보 필드: "+", ".join(sorted(unknown)))
    result={field:value.get(field,"UNKNOWN") for field in ALLOWED_CLINICAL_FIELDS}
    result["symptom_codes"]=value.get("symptom_codes",[]) or []
    return result

def priority_decision(instance_results:list[dict],protocol_status:str,thresholds:dict)->dict:
    reasons=[]
    if any(x.get("quality_status")=="REJECT" for x in instance_results):return {"status":"QUALITY_REJECTED","reasons":["QUALITY_REJECTED"]}
    regions={x.get("region","UNKNOWN") for x in instance_results}
    if len(regions)>1:reasons.append("INSTANCE_REGION_CONFLICT")
    if protocol_status in {"MISSING_VIEW","PARTIAL"}:reasons.append("REQUIRED_VIEW_MISSING")
    if any(x.get("ood_status")!="IN_DISTRIBUTION" for x in instance_results):reasons.append("OUT_OF_DISTRIBUTION")
    if reasons:return {"status":"REVIEW_REQUIRED","reasons":reasons}
    threshold=float(thresholds.get("high_priority_finding_probability",.8))
    if any(float(x.get("max_finding_probability",0))>=threshold for x in instance_results):return {"status":"HIGH_PRIORITY_REVIEW","reasons":["HIGH_FINDING_SCORE_REVIEW_REQUEST"]}
    return {"status":"ROUTINE","reasons":["NO_PRIORITY_TRIGGER"]}
