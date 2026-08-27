import torch
from xray_classifier.model import build_model
from xray_classifier.metrics import classification_metrics
def test_output_dimension(): assert build_model()(torch.randn(2,3,224,224)).shape==(2,8)
def test_metrics():
 r=classification_metrics([0,1],__import__('numpy').array([[.9,.1],[.2,.8]]));assert r['accuracy']==1 and r['macro_f1']==1
