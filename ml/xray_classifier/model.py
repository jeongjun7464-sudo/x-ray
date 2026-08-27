import torch
from torch import nn
from torchvision.models import densenet121
from . import CLASSES
def build_model(pretrained=False):
    model=densenet121(weights="DEFAULT" if pretrained else None); model.classifier=nn.Linear(model.classifier.in_features,len(CLASSES)); return model
def save_checkpoint(path,model,optimizer,epoch,config): torch.save({"model":model.state_dict(),"optimizer":optimizer.state_dict(),"epoch":epoch,"config":config},path)
def load_checkpoint(path,model,optimizer=None,device="cpu"):
    ckpt=torch.load(path,map_location=device,weights_only=False); model.load_state_dict(ckpt["model"])
    if optimizer and ckpt.get("optimizer"): optimizer.load_state_dict(ckpt["optimizer"])
    return ckpt
