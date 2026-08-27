import argparse,json,torch
from PIL import Image
from torchvision import transforms
from xray_classifier import CLASSES
from xray_classifier.model import build_model,load_checkpoint
def main():
 p=argparse.ArgumentParser();p.add_argument('image');p.add_argument('--checkpoint',required=True);a=p.parse_args();device='cuda' if torch.cuda.is_available() else 'cpu';m=build_model().to(device);load_checkpoint(a.checkpoint,m,device=device);m.eval();x=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor()])(Image.open(a.image).convert('RGB')).unsqueeze(0).to(device)
 with torch.no_grad(): prob=torch.softmax(m(x),1)[0]; vals,idx=prob.topk(3)
 print(json.dumps([{'class':CLASSES[i],'confidence':float(v)} for v,i in zip(vals,idx)],indent=2))
if __name__=='__main__':main()
