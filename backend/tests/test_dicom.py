from io import BytesIO
import numpy as np, pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
from app.services.dicom_service import anonymize, pixel_to_uint8, read_dicom
def make_dicom(mono="MONOCHROME2"):
    meta=FileMetaDataset(); meta.TransferSyntaxUID=ExplicitVRLittleEndian; meta.MediaStorageSOPClassUID=SecondaryCaptureImageStorage; meta.MediaStorageSOPInstanceUID=generate_uid()
    ds=FileDataset(None,{},file_meta=meta,preamble=b"\0"*128); ds.SOPClassUID=meta.MediaStorageSOPClassUID; ds.SOPInstanceUID=meta.MediaStorageSOPInstanceUID; ds.Rows=64; ds.Columns=64; ds.SamplesPerPixel=1; ds.PhotometricInterpretation=mono; ds.BitsAllocated=16; ds.BitsStored=12; ds.HighBit=11; ds.PixelRepresentation=0; ds.PatientName="SECRET"; ds.PatientID="123"; ds.PixelData=np.arange(4096,dtype=np.uint16).tobytes(); out=BytesIO(); ds.save_as(out,enforce_file_format=True); return out.getvalue()
def test_dicom_and_anonymize():
    ds=read_dicom(make_dicom()); assert pixel_to_uint8(ds).shape==(64,64); clean=anonymize(ds); assert "PatientName" not in clean and "PatientID" not in clean
def test_monochrome1_inverts():
    a=pixel_to_uint8(read_dicom(make_dicom("MONOCHROME1"))); b=pixel_to_uint8(read_dicom(make_dicom())); assert np.allclose(a+b,255,atol=1)
