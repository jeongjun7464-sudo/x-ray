from xray_findings import FindingInferenceEngine
from xray_findings.gradcam import FindingGradCAM
from xray_findings.postprocess import apply_thresholds
from xray_findings.thresholds import DEFAULT_THRESHOLDS,FINDING_LABELS

def test_dummy_multilabel_is_reproducible():
    engine=FindingInferenceEngine();first=engine.predict(b"synthetic-xray");second=engine.predict(b"synthetic-xray")
    assert first==second and first.model_version=="dummy-finding-v1" and first.dummy_mode
    assert len(first.findings)==10 and all(0<=x.probability<=1 for x in first.findings)

def test_thresholds_and_explanation_support():
    probabilities={code:.5 for code in FINDING_LABELS};result=apply_thresholds(probabilities,DEFAULT_THRESHOLDS)
    assert all(x.positive for x in result)
    gradcam=FindingGradCAM(dummy_mode=True);assert not gradcam.available
