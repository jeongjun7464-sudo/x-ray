from __future__ import annotations
import math

DRIFT_FIELDS=("brightness_distribution","contrast_distribution","resolution_distribution","region_distribution","equipment_distribution","institution_distribution","finding_probability_distribution")
RATE_FIELDS=("ood_rate","unknown_rate","correction_rate","quality_reject_rate","retrieval_degradation_rate","citation_failure_rate")

def _distribution(value):
    if not isinstance(value,dict) or not value:return None
    total=sum(max(0,float(x)) for x in value.values())
    return {str(k):max(0,float(v))/total for k,v in value.items()} if total else None

def jensen_shannon(left,right):
    p,q=_distribution(left),_distribution(right)
    if p is None or q is None:return None
    keys=set(p)|set(q);m={k:(p.get(k,0)+q.get(k,0))/2 for k in keys}
    def kl(a):return sum(v*math.log(v/m[k],2) for k,v in a.items() if v>0 and m[k]>0)
    return (kl(p)+kl(q))/2

def relative_change(base,current):
    try:
        b,c=float(base),float(current)
    except (TypeError,ValueError):return None
    return abs(c-b)/max(abs(b),0.01)

def evaluate_drift(baseline,current,baseline_size,current_size,min_samples=30,warning_threshold=.10,critical_threshold=.25):
    if not baseline or not current:return {"status":"NOT_MEASURED","severity":"NOT_MEASURED","scores":{},"reason":"기준선 또는 현재 측정값이 없습니다.","performance_claim":False}
    if baseline_size<min_samples or current_size<min_samples:return {"status":"INSUFFICIENT_DATA","severity":"INSUFFICIENT_DATA","scores":{},"reason":f"최소 표본 {min_samples}건이 필요합니다.","performance_claim":False}
    scores={}
    for field in DRIFT_FIELDS:
        score=jensen_shannon(baseline.get(field),current.get(field))
        if score is not None:scores[field]=round(score,6)
    for field in RATE_FIELDS:
        score=relative_change(baseline.get(field),current.get(field))
        if score is not None:scores[field]=round(score,6)
    if not scores:return {"status":"NOT_MEASURED","severity":"NOT_MEASURED","scores":{},"reason":"비교 가능한 지표가 없습니다.","performance_claim":False}
    maximum=max(scores.values());status="CRITICAL" if maximum>=critical_threshold else "WARNING" if maximum>=warning_threshold else "STABLE"
    return {"status":status,"severity":status,"scores":scores,"maximum_score":maximum,"thresholds":{"warning":warning_threshold,"critical":critical_threshold},"reason":"분포·비율 변화이며 정답 기반 성능 저하 판정이 아닙니다.","performance_claim":False}
