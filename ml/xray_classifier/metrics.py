import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
def expected_calibration_error(y_true,probs,bins=10):
    conf=probs.max(1); pred=probs.argmax(1); total=0.0
    for lo in np.linspace(0,1,bins,endpoint=False):
        mask=(conf>lo)&(conf<=lo+1/bins)
        if mask.any(): total+=mask.mean()*abs((pred[mask]==y_true[mask]).mean()-conf[mask].mean())
    return float(total)
def classification_metrics(y_true,probs):
    pred=probs.argmax(1); p,r,f,_=precision_recall_fscore_support(y_true,pred,average=None,zero_division=0)
    return {"accuracy":accuracy_score(y_true,pred),"macro_f1":float(f.mean()),"precision":p.tolist(),"recall":r.tolist(),"f1":f.tolist(),"confusion_matrix":confusion_matrix(y_true,pred).tolist(),"ece":expected_calibration_error(np.asarray(y_true),probs)}
