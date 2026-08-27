from app.core.config import settings
def review_decision(top: list[dict], laterality: str, view: str, metadata_body: str | None = None) -> tuple[bool, list[str]]:
    reasons=[]
    if top[0]["confidence"] < settings.auto_classify_min_confidence: reasons.append("LOW_CONFIDENCE")
    if top[0]["confidence"]-top[1]["confidence"] < settings.uncertainty_margin: reasons.append("AMBIGUOUS_PREDICTION")
    if laterality == "UNKNOWN": reasons.append("LATERALITY_UNKNOWN")
    if view == "UNKNOWN": reasons.append("VIEW_UNKNOWN")
    if metadata_body and top[0]["class"] not in metadata_body and metadata_body not in top[0]["class"]: reasons.append("METADATA_CONFLICT")
    return bool(reasons), reasons
