import torch
from torch import nn
from xray_classifier.gradcam import GradCAM
from xray_classifier.model import build_model
from xray_classifier.metrics import classification_metrics
def test_output_dimension(): assert build_model()(torch.randn(2,3,224,224)).shape==(2,8)
def test_metrics():
 r=classification_metrics([0,1],__import__('numpy').array([[.9,.1],[.2,.8]]));assert r['accuracy']==1 and r['macro_f1']==1
def test_gradcam_heatmap():
 class Tiny(nn.Module):
  def __init__(self): super().__init__(); self.conv=nn.Conv2d(1,2,3,padding=1); self.head=nn.Linear(2,2)
  def forward(self,x): return self.head(self.conv(x).mean((2,3)))
 model=Tiny(); cam=GradCAM(model,model.conv); heat=cam(torch.randn(1,1,16,16)); cam.close(); assert heat.shape==(16,16) and heat.min()>=0 and heat.max()<=1

