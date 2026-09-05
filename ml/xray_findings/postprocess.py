from .schemas import FindingPrediction
from .thresholds import FINDING_LABELS

def apply_thresholds(probabilities:dict[str,float],thresholds:dict[str,float])->list[FindingPrediction]:
    return [FindingPrediction(code,display,round(max(0.0,min(1.0,float(probabilities[code]))),6),thresholds[code],probabilities[code]>=thresholds[code]) for code,display in FINDING_LABELS.items()]

def near_threshold(findings:list[FindingPrediction],margin:float=.08)->bool:
    return any(abs(x.probability-x.threshold)<=margin for x in findings)
