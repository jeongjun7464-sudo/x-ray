import argparse,json,numpy as np,torch
from torch.utils.data import DataLoader
from torchvision import transforms
from xray_classifier.dataset import XRayDataset
from xray_classifier.metrics import classification_metrics
from xray_classifier.model import build_model,load_checkpoint
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--checkpoint',required=True);a=p.parse_args();device='cuda' if torch.cuda.is_available() else 'cpu';model=build_model().to(device);load_checkpoint(a.checkpoint,model,device=device);model.eval();ds=XRayDataset(manifest=a.manifest,transform=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor()]));ys=[];ps=[]
 with torch.no_grad():
  for x,y,_ in DataLoader(ds,batch_size=16):ps.extend(torch.softmax(model(x.to(device)),1).cpu().numpy());ys.extend(y.numpy())
 print(json.dumps(classification_metrics(ys,np.asarray(ps)),indent=2))
if __name__=='__main__':main()
