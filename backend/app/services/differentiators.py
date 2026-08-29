import math
from dataclasses import asdict, dataclass
import numpy as np

ROUTES = {
    "CHEST": "CHEST_ANALYSIS", "SPINE": "SPINE_ANALYSIS",
    "HAND_WRIST": "HAND_WRIST_ANALYSIS", "KNEE": "KNEE_ANALYSIS",
}

@dataclass(frozen=True)
class ExtendedAssessment:
    quality_status: str
    quality_score: float
    quality_reasons: tuple[str, ...]
    distribution_status: str
    entropy: float
    metadata_status: str
    metadata_warnings: tuple[str, ...]
    routing_target: str
    priority: str

    def dict(self): return asdict(self)

def _metadata_tokens(ds) -> str:
    if ds is None: return ""
    names=("BodyPartExamined","StudyDescription","SeriesDescription")
    return " ".join(str(getattr(ds,n,"")) for n in names).upper()

def assess_extended(pixels, top, ds=None, base_quality=None) -> ExtendedAssessment:
    arr=np.asarray(pixels,dtype=np.float32); arr=arr.mean(-1) if arr.ndim==3 else arr
    if arr.max()>1: arr/=255
    reasons=list(getattr(base_quality,"reasons",()))
    mean=float(arr.mean()); sharp=float(np.var(np.diff(arr,axis=0))) if arr.shape[0]>1 else 0
    if mean<.05: reasons.append("TOO_DARK")
    if mean>.95: reasons.append("TOO_BRIGHT")
    if sharp<1e-5: reasons.append("BLUR_OR_EMPTY")
    if min(arr.shape[-2:])<64: reasons.append("UNSUPPORTED_RESOLUTION")
    quality_score=max(0.0,1.0-.18*len(set(reasons)))
    quality_status="REJECT" if any(x in reasons for x in ("BLUR_OR_EMPTY","UNSUPPORTED_RESOLUTION")) else "WARNING" if reasons else "PASS"
    probs=np.asarray([x["confidence"] for x in top],dtype=float); remainder=max(0,1-probs.sum()); probs=np.append(probs,remainder) if remainder else probs
    entropy=float(-sum(p*math.log(max(p,1e-9)) for p in probs))
    modality=str(getattr(ds,"Modality","DX") if ds is not None else "DX").upper()
    if modality not in {"DX","CR","RG"}: distribution="OUT_OF_DISTRIBUTION"
    elif top[0]["confidence"]<.35 or entropy>1.25: distribution="UNKNOWN"
    else: distribution="IN_DISTRIBUTION"
    tokens=_metadata_tokens(ds); predicted=top[0]["class"]; warnings=[]
    if ds is not None and not tokens.strip(): warnings.append("METADATA_MISSING")
    known=[x for x in ("CHEST","KNEE","SPINE","HAND","WRIST","FOOT","PELVIS","ABDOMEN") if x in tokens]
    conflict=bool(known and not any(x in predicted or predicted in x for x in known))
    if conflict: warnings.append("METADATA_AI_CONFLICT")
    metadata_status="CONFLICT" if conflict else "MISSING" if "METADATA_MISSING" in warnings else "MATCH"
    review=distribution!="IN_DISTRIBUTION" or quality_status!="PASS" or metadata_status!="MATCH"
    route="REVIEW_QUEUE" if review else ROUTES.get(predicted,"REVIEW_QUEUE")
    priority="HIGH" if distribution=="OUT_OF_DISTRIBUTION" or quality_status=="REJECT" or conflict else "MEDIUM" if review else "LOW"
    return ExtendedAssessment(quality_status,round(quality_score,4),tuple(sorted(set(reasons))),distribution,round(entropy,4),metadata_status,tuple(warnings),route,priority)

def mock_model_comparison(file_hash, base_top):
    names=[("DenseNet121","production"),("EfficientNetV2","experiment"),("ConvNeXt","experiment"),("ONNX Runtime","experiment")]
    out=[]
    for i,(name,role) in enumerate(names):
        top=[dict(x) for x in base_top]; shift=((int(file_hash[i:i+2],16)%7)-3)/100
        top[0]["confidence"]=round(max(0,min(1,top[0]["confidence"]+shift)),4)
        out.append({"model":name,"role":role,"model_version":f"mock-{name.lower()}-v1","top_predictions":top,"prediction":top[0]["class"],"confidence":top[0]["confidence"],"inference_time_ms":8+i*4,"mock_mode":True})
    return out
