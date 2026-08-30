import hashlib
import hmac
import io
import json
import math
import os
import time
import zipfile
from datetime import datetime, timezone

import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

DEFAULT_PROTOCOLS = {
    "CHEST": ({"PA", "AP"}, {"LATERAL"}, "ANY_REQUIRED"),
    "KNEE": ({"AP", "LATERAL"}, set(), "ALL_REQUIRED"),
    "HAND_WRIST": ({"PA", "OBLIQUE", "LATERAL"}, set(), "ALL_REQUIRED"),
    "ANKLE": ({"AP", "MORTISE", "LATERAL"}, set(), "ALL_REQUIRED"),
    "CERVICAL_SPINE": ({"AP", "LATERAL"}, set(), "ALL_REQUIRED"),
}

def digest(value: object) -> str:
    return hashlib.sha256(str(value or "MISSING").encode()).hexdigest()

def dicom_group_metadata(data: bytes) -> dict:
    ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True)
    return {
        "study_uid_hash": digest(getattr(ds, "StudyInstanceUID", None)),
        "series_uid_hash": digest(getattr(ds, "SeriesInstanceUID", None)),
        "sop_uid_hash": digest(getattr(ds, "SOPInstanceUID", None)),
        "anonymous_accession": digest(getattr(ds, "AccessionNumber", None))[:16],
        "study_date": str(getattr(ds, "StudyDate", "")) or None,
        "series_number": _int(getattr(ds, "SeriesNumber", None)),
        "instance_number": _int(getattr(ds, "InstanceNumber", None)),
        "view_position": str(getattr(ds, "ViewPosition", "UNKNOWN")).upper(),
        "laterality": str(getattr(ds, "Laterality", "UNKNOWN")).upper(),
        "body_part": str(getattr(ds, "BodyPartExamined", "UNKNOWN")).upper(),
    }

def _int(value):
    try: return int(value)
    except (TypeError, ValueError): return None

def protocol_check(region: str, views: list[str], required: list[str], optional: list[str], any_required: bool = False) -> dict:
    observed = {v.upper() for v in views if v and v != "UNKNOWN"}
    req, opt = set(required), set(optional)
    if not req: return {"status":"UNKNOWN_PROTOCOL","missing":[],"extra":sorted(observed),"disclaimer":"자료 정리와 검토 지원용이며 촬영 재지시가 아닙니다."}
    missing = [] if (observed & req if any_required else req <= observed) else sorted(req - observed)
    extra = sorted(observed - req - opt)
    status = "MISSING_VIEW" if missing else "EXTRA_VIEW" if extra else "COMPLETE"
    if observed and missing: status = "PARTIAL"
    return {"status":status,"missing":missing,"extra":extra,"observed":sorted(observed),"disclaimer":"자료 정리와 검토 지원용이며 촬영 재지시가 아닙니다."}

def generated_tags(region: str, view: str, laterality: str, quality: str, model_version: str) -> list[dict]:
    values=[(region,"AI_PREDICTION"),(view,"DICOM_VIEW_POSITION"),(laterality,"DICOM_LATERALITY"),(quality,"QUALITY_ENGINE"),(model_version,"MODEL_VERSION")]
    return [{"value":v,"source":s,"editable":True} for v,s in values if v and v != "UNKNOWN"]

def apply_rules(context: dict, rules: list[object]) -> dict:
    for rule in sorted(rules, key=lambda x: x.priority):
        if not rule.active: continue
        ok=True
        for key, expected in (rule.conditions or {}).items():
            actual=context.get(key)
            if key.endswith("_gte"): ok &= float(context.get(key[:-4],0)) >= float(expected)
            elif key.endswith("_lt"): ok &= float(context.get(key[:-3],0)) < float(expected)
            else: ok &= actual == expected
        if ok: return {"destination":rule.destination,"rule_id":rule.id,"rule_version":rule.version}
    return {"destination":"MANUAL_REVIEW","rule_id":None,"rule_version":None}

def uncertainty(probabilities: list[float]) -> dict:
    ps=[max(1e-9,float(x)) for x in probabilities]
    entropy=-sum(p*math.log(p) for p in ps)
    ordered=sorted(ps,reverse=True)
    return {"predictive_entropy":entropy,"probability_margin":ordered[0]-ordered[1] if len(ordered)>1 else ordered[0]}

def fhir_bundle(prediction, study_id: str | None = None) -> dict:
    now=datetime.now(timezone.utc).isoformat()
    resources=[
      {"resourceType":"ImagingStudy","id":study_id or prediction.id,"status":"available","description":"Synthetic/local de-identified imaging study"},
      {"resourceType":"Observation","id":f"obs-{prediction.id}","status":"preliminary","code":{"text":"Anatomical region classifier output"},"valueString":prediction.anatomical_region,"extension":[{"url":"urn:xray:confidence","valueDecimal":prediction.confidence}]},
      {"resourceType":"DiagnosticReport","id":f"report-{prediction.id}","status":"preliminary","code":{"text":"Research-only AI routing result"},"conclusion":"Not a diagnosis; anatomical routing support only."},
      {"resourceType":"DocumentReference","id":f"doc-{prediction.id}","status":"current","description":"Anonymous result report"},
      {"resourceType":"AuditEvent","id":f"audit-{prediction.id}","recorded":now,"action":"E","outcome":"0"},
      {"resourceType":"Provenance","id":f"prov-{prediction.id}","recorded":now,"target":[{"reference":f"Observation/obs-{prediction.id}"}]},
    ]
    return {"resourceType":"Bundle","type":"collection","entry":[{"resource":x} for x in resources],"meta":{"tag":[{"system":"urn:xray","code":"SYNTHETIC-LOCAL"}]}}

def experimental_sr(prediction) -> bytes:
    meta=FileMetaDataset(); meta.MediaStorageSOPClassUID="1.2.840.10008.5.1.4.1.1.88.33"; meta.MediaStorageSOPInstanceUID=generate_uid(); meta.TransferSyntaxUID=ExplicitVRLittleEndian
    ds=FileDataset(None,{},file_meta=meta,preamble=b"\0"*128); ds.SOPClassUID=meta.MediaStorageSOPClassUID; ds.SOPInstanceUID=meta.MediaStorageSOPInstanceUID
    ds.Modality="SR"; ds.SeriesInstanceUID=generate_uid(); ds.StudyInstanceUID=generate_uid(); ds.PatientName="SYNTHETIC^ANONYMOUS"; ds.PatientID="ANONYMOUS"; ds.ContentDate=datetime.now().strftime("%Y%m%d"); ds.ContentTime=datetime.now().strftime("%H%M%S")
    ds.SeriesDescription="EXPERIMENTAL RESEARCH-ONLY AI ROUTING SR"; ds.CompletionFlag="PARTIAL"; ds.VerificationFlag="UNVERIFIED"
    root=Dataset(); root.ValueType="CONTAINER"; root.RelationshipType="CONTAINS"; root.ContinuityOfContent="SEPARATE"; root.ConceptNameCodeSequence=[_code("X-RAY-ROUTING","99LOCAL","Research-only anatomical routing result")]
    root.ContentSequence=[]
    for name,value in [("Anonymous analysis ID",prediction.id),("Region",prediction.anatomical_region),("Confidence",f"{prediction.confidence:.4f}"),("Model",prediction.model_version),("Review required",str(prediction.review_required))]:
        item=Dataset(); item.ValueType="TEXT"; item.RelationshipType="CONTAINS"; item.ConceptNameCodeSequence=[_code(digest(name)[:8],"99LOCAL",name)]; item.TextValue=value; root.ContentSequence.append(item)
    ds.ContentSequence=[root]; out=io.BytesIO(); ds.save_as(out,enforce_file_format=True); return out.getvalue()

def _code(value,scheme,meaning):
    x=Dataset(); x.CodeValue=value; x.CodingSchemeDesignator=scheme; x.CodeMeaning=meaning; return x

def inspect_zip(data: bytes, max_files=100, max_uncompressed=100*1024*1024) -> list[dict]:
    if len(data)>25*1024*1024: raise ValueError("ZIP 파일 크기 제한을 초과했습니다.")
    try: z=zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc: raise ValueError("손상된 ZIP 파일입니다.") from exc
    infos=z.infolist()
    if len(infos)>max_files: raise ValueError("ZIP 파일 개수 제한을 초과했습니다.")
    if any(i.filename.startswith(("/","\\")) or ".." in i.filename.replace("\\","/").split("/") for i in infos): raise ValueError("ZIP 경로 조작이 탐지되었습니다.")
    if any((i.external_attr >> 16) & 0o170000 == 0o120000 for i in infos): raise ValueError("ZIP 심볼릭 링크는 허용되지 않습니다.")
    total=sum(i.file_size for i in infos)
    if total>max_uncompressed or total>max(1,len(data))*100: raise ValueError("ZIP bomb 또는 압축 해제 크기 초과가 탐지되었습니다.")
    allowed={".dcm",".png",".jpg",".jpeg"}; result=[]
    for i in infos:
        ext=os.path.splitext(i.filename)[1].lower(); reason=None
        if ext==".zip": reason="NESTED_ARCHIVE_BLOCKED"
        elif ext not in allowed or i.is_dir(): reason="UNSUPPORTED_FILE"
        result.append({"name":os.path.basename(i.filename),"size":i.file_size,"accepted":reason is None,"reason":reason})
    return result

def webhook_signature(payload: dict, timestamp: int, secret: str) -> str:
    body=json.dumps(payload,separators=(",",":"),sort_keys=True).encode()
    return hmac.new(secret.encode(),str(timestamp).encode()+b"."+body,hashlib.sha256).hexdigest()
