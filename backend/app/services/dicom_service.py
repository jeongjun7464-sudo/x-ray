from copy import deepcopy
from io import BytesIO
import numpy as np
import pydicom
from PIL import Image
from pydicom.dataset import Dataset
from app.core.constants import LATERALITIES, VIEWS

PHI_KEYWORDS = ["PatientName", "PatientID", "PatientBirthDate", "PatientAddress", "PatientTelephoneNumbers", "InstitutionName", "ReferringPhysicianName", "OtherPatientIDs", "AccessionNumber"]

class DicomDecodeError(ValueError): pass

def read_dicom(data: bytes) -> Dataset:
    try:
        ds = pydicom.dcmread(BytesIO(data), force=False)
    except Exception as exc:
        raise DicomDecodeError("유효한 DICOM 파일이 아닙니다.") from exc
    if "PixelData" not in ds:
        raise DicomDecodeError("DICOM에 픽셀 데이터가 없습니다.")
    return ds

def pixel_to_uint8(ds: Dataset) -> np.ndarray:
    try: arr = ds.pixel_array.astype(np.float32)
    except Exception as exc: raise DicomDecodeError("압축 방식 또는 전송 구문을 디코딩할 수 없습니다.") from exc
    arr = arr * float(getattr(ds, "RescaleSlope", 1)) + float(getattr(ds, "RescaleIntercept", 0))
    wc, ww = getattr(ds, "WindowCenter", None), getattr(ds, "WindowWidth", None)
    if wc is not None and ww is not None:
        wc = float(wc[0] if hasattr(wc, "__len__") else wc); ww = max(float(ww[0] if hasattr(ww, "__len__") else ww), 1)
        low, high = wc - ww / 2, wc + ww / 2
    else: low, high = np.percentile(arr, (1, 99))
    arr = np.clip((arr-low) / max(high-low, 1e-6), 0, 1)
    if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1": arr = 1-arr
    return (arr*255).astype(np.uint8)

def preview_png(ds: Dataset) -> bytes:
    out = BytesIO(); Image.fromarray(pixel_to_uint8(ds)).save(out, "PNG"); return out.getvalue()
def metadata_orientation(ds: Dataset) -> tuple[str, str, str | None]:
    lat = LATERALITIES.get(str(getattr(ds, "ImageLaterality", getattr(ds, "Laterality", ""))).upper(), "UNKNOWN")
    view = VIEWS.get(str(getattr(ds, "ViewPosition", "")).upper(), "UNKNOWN")
    body = str(getattr(ds, "BodyPartExamined", "")).upper() or None
    return lat, view, body
def anonymize(ds: Dataset) -> Dataset:
    clean = deepcopy(ds)
    for key in PHI_KEYWORDS:
        if key in clean: del clean[key]
    clean.remove_private_tags()
    return clean
