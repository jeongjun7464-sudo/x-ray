from io import BytesIO
import numpy as np
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

def generate_synthetic_dicom(variant="normal") -> bytes:
    meta=FileMetaDataset();meta.TransferSyntaxUID=ExplicitVRLittleEndian;meta.MediaStorageSOPClassUID=SecondaryCaptureImageStorage;meta.MediaStorageSOPInstanceUID=generate_uid()
    ds=FileDataset(None,{},file_meta=meta,preamble=b"\0"*128);ds.SOPClassUID=meta.MediaStorageSOPClassUID;ds.SOPInstanceUID=meta.MediaStorageSOPInstanceUID
    size=1024 if variant=="large" else 256;ds.Rows=size;ds.Columns=size;ds.SamplesPerPixel=1;ds.PhotometricInterpretation="MONOCHROME1" if variant=="monochrome1" else "MONOCHROME2";ds.BitsAllocated=16;ds.BitsStored=12;ds.HighBit=11;ds.PixelRepresentation=0
    ds.Modality="CT" if variant=="wrong_modality" else "DX";ds.BodyPartExamined="KNEE" if variant=="metadata_conflict" else "CHEST";ds.StudyDescription="SYNTHETIC DATA - NOT FOR CLINICAL USE";ds.PatientName="SYNTHETIC^PATIENT";ds.PatientID="SYNTHETIC-ONLY"
    if variant!="no_pixel":
        y,x=np.mgrid[-1:1:complex(size),-1:1:complex(size)];arr=(4095*np.exp(-2*(x*x+y*y))).astype(np.uint16);ds.PixelData=arr.tobytes()
    out=BytesIO();ds.save_as(out,enforce_file_format=True);data=out.getvalue()
    return data[:200] if variant=="corrupt" else data
