import numpy as np
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, cohen_kappa_score,
    confusion_matrix, matthews_corrcoef, precision_recall_fscore_support)
def expected_calibration_error(y_true,probs,bins=10):
    conf=probs.max(1); pred=probs.argmax(1); total=0.0
    for lo in np.linspace(0,1,bins,endpoint=False):
        mask=(conf>lo)&(conf<=lo+1/bins)
        if mask.any(): total+=mask.mean()*abs((pred[mask]==y_true[mask]).mean()-conf[mask].mean())
    return float(total)
def classification_metrics(y_true,probs):
    pred=probs.argmax(1); p,r,f,_=precision_recall_fscore_support(y_true,pred,average=None,zero_division=0)
    _,_,weighted_f1,_=precision_recall_fscore_support(y_true,pred,average="weighted",zero_division=0)
    top3=np.argsort(probs,axis=1)[:,-min(3,probs.shape[1]):]
    brier=float(np.mean(np.sum((probs-np.eye(probs.shape[1])[np.asarray(y_true)])**2,axis=1)))
    return {"accuracy":accuracy_score(y_true,pred),"balanced_accuracy":balanced_accuracy_score(y_true,pred),
        "macro_f1":float(f.mean()),"weighted_f1":float(weighted_f1),"top3_accuracy":float(np.mean([y in row for y,row in zip(y_true,top3)])),
        "cohen_kappa":cohen_kappa_score(y_true,pred),"mcc":matthews_corrcoef(y_true,pred),"brier_score":brier,
        "precision":p.tolist(),"recall":r.tolist(),"f1":f.tolist(),"confusion_matrix":confusion_matrix(y_true,pred).tolist(),"ece":expected_calibration_error(np.asarray(y_true),probs)}

def bootstrap_accuracy_ci(y_true, probs, iterations=1000, seed=42):
    rng=np.random.default_rng(seed); y=np.asarray(y_true); pred=np.asarray(probs).argmax(1); values=[]
    for _ in range(iterations):
        idx=rng.integers(0,len(y),len(y)); values.append(accuracy_score(y[idx],pred[idx]))
    return {"lower":float(np.percentile(values,2.5)),"upper":float(np.percentile(values,97.5)),"iterations":iterations}

