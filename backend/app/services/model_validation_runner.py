VALIDATION_TYPES={"FUNCTIONAL","PERFORMANCE","ROBUSTNESS","FAIRNESS","SAFETY","SECURITY","COMPATIBILITY","REPRODUCIBILITY"}
def evaluate_metrics(measurements:list[dict],thresholds:dict,minimum_sample_size:int)->list[dict]:
    output=[]
    for item in measurements:
        name=str(item.get("metric_name","UNKNOWN"));value=item.get("value");sample=int(item.get("sample_size",0));threshold=thresholds.get(name)
        if value is None:status="NOT_MEASURED";passed=None
        elif sample<minimum_sample_size:status="INSUFFICIENT_DATA";passed=None
        elif threshold is None:status="MANUAL_REVIEW_REQUIRED";passed=None
        else:passed=float(value)>=float(threshold);status="PASS" if passed else "FAIL"
        output.append({**item,"metric_name":name,"threshold":threshold,"sample_size":sample,"status":status,"passed":passed})
    return output

def validation_status(metrics:list[dict])->str:
    if not metrics or any(x["status"] in {"NOT_MEASURED","INSUFFICIENT_DATA","FAIL","MANUAL_REVIEW_REQUIRED"} for x in metrics):return "VALIDATION_FAILED"
    return "APPROVAL_REQUIRED"
