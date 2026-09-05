from __future__ import annotations
try:
    import torch
    from torch import nn
except ImportError:
    torch=None;nn=object

class MultiLabelFindingModel(nn.Module if torch else object):
    """Shared sigmoid-logit interface for approved PyTorch checkpoints."""
    def __init__(self,backbone,num_findings:int=10):
        if not torch: raise RuntimeError("PyTorch is required for real-model mode")
        super().__init__();self.backbone=backbone;self.num_findings=num_findings
    def forward(self,x):return self.backbone(x)
