from pathlib import Path
import subprocess,sys
blocked=(".pt",".pth",".onnx",".safetensors",".dcm",".dicom",".nii",".nii.gz")
files=subprocess.check_output(["git","ls-files"],text=True).splitlines();bad=[]
for name in files:
    lower=name.lower()
    if lower.endswith(blocked) and not lower.startswith("sample_data/synthetic-allowlist/"):bad.append(name)
    if lower.endswith((".env",".pem",".key")):bad.append(name)
if bad:
    print("Blocked model/medical/secret artifacts:",*sorted(set(bad)),sep="\n- ");sys.exit(1)
print(f"repository artifact policy passed ({len(files)} tracked files checked)")
