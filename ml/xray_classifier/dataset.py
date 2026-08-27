from pathlib import Path
import pandas as pd
from PIL import Image
from torch.utils.data import Dataset
from . import CLASSES

REQUIRED=["file_path","anatomical_region","laterality","view_position","patient_group_id","institution_id"]
class XRayDataset(Dataset):
    def __init__(self, root: str|None=None, manifest: str|None=None, transform=None):
        self.transform=transform
        if manifest:
            df=pd.read_csv(manifest); missing=set(REQUIRED)-set(df.columns)
            if missing: raise ValueError(f"manifest missing columns: {sorted(missing)}")
            self.items=df.to_dict("records")
        elif root:
            self.items=[{"file_path":str(p),"anatomical_region":c} for c in CLASSES for p in Path(root,c).glob("*") if p.suffix.lower() in {'.png','.jpg','.jpeg'}]
        else: raise ValueError("root or manifest is required")
    def __len__(self): return len(self.items)
    def __getitem__(self,i):
        row=self.items[i]; image=Image.open(row["file_path"]).convert("RGB"); image=self.transform(image) if self.transform else image
        return image,CLASSES.index(row["anatomical_region"]),row
def assert_no_patient_leakage(*manifests: str):
    seen={}
    for split,path in enumerate(manifests):
        for pid in pd.read_csv(path).patient_group_id.astype(str):
            if pid in seen: raise ValueError(f"patient leakage: {pid} in splits {seen[pid]} and {split}")
            seen[pid]=split
