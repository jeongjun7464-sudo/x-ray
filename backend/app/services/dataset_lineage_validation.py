import hashlib,json

def validate_lineage(training:dict,test:dict)->dict:
    if not training or not test:return {"status":"NOT_VERIFIABLE","reason_codes":["DATASET_VERSION_NOT_FOUND"]}
    def values(manifest,key):return {str(x.get(key)) for x in manifest.get("manifest",[]) if x.get(key)}
    image_overlap=values(training,"image_sha256")&values(test,"image_sha256")
    subject_overlap=values(training,"subject_hash")&values(test,"subject_hash")
    unapproved=[x for x in training.get("manifest",[])+test.get("manifest",[]) if x.get("label_status") not in {None,"APPROVED"}]
    phi=any(any(k.lower() in {"patientname","patientid","name","phone","address"} for k in x) for x in training.get("manifest",[])+test.get("manifest",[]))
    reasons=[]
    if image_overlap or subject_overlap:reasons.append("DATA_LEAKAGE_DETECTED")
    if unapproved:reasons.append("UNAPPROVED_LABEL_INCLUDED")
    if phi:reasons.append("PHI_FIELD_DETECTED")
    for item in (training,test):
        canonical=json.dumps(item.get("manifest",[]),sort_keys=True,separators=(",",":")).encode();expected=item.get("manifest_sha256")
        if expected and hashlib.sha256(canonical).hexdigest()!=expected:reasons.append("MANIFEST_HASH_MISMATCH")
    return {"status":"FAILED" if reasons else "VERIFIED","reason_codes":sorted(set(reasons)),"image_overlap_count":len(image_overlap),"subject_overlap_count":len(subject_overlap),"uses_anonymous_subject_hash":True}
