from io import BytesIO
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import generate_uid
from .schemas import IntegrationResult
from .security import anonymous_uid

# A fresh allowlisted dataset also excludes nested sequences, private tags,
# descriptive text and source file meta information.
RETAIN = {"SOPClassUID", "Modality", "Rows", "Columns", "SamplesPerPixel",
          "PhotometricInterpretation", "BitsAllocated", "BitsStored", "HighBit",
          "PixelRepresentation", "PixelData", "NumberOfFrames", "PlanarConfiguration"}

def deidentify(data: bytes) -> IntegrationResult:
    if len(data) > 20 * 1024 * 1024 or len(data) < 132 or data[128:132] != b"DICM":
        return IntegrationResult("DEGRADED", "INVALID_DICOM")
    try:
        source = pydicom.dcmread(BytesIO(data))
        hashes = {key: anonymous_uid(str(source.get(key, ""))) for key in ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID")}
        if "PixelData" not in source:
            return IntegrationResult("DEGRADED", "EMPTY_PIXEL_DATA")
        if source.get("Modality") not in {"DX", "CR"}:
            return IntegrationResult("MANUAL_REVIEW_REQUIRED", "UNSUPPORTED_MODALITY")
        meta = FileMetaDataset()
        meta.TransferSyntaxUID = source.file_meta.TransferSyntaxUID
        target = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
        for element in source:
            if element.keyword in RETAIN:
                target.add(element)
        for key in hashes:
            setattr(target, key, generate_uid())
        meta.MediaStorageSOPClassUID = target.SOPClassUID
        meta.MediaStorageSOPInstanceUID = target.SOPInstanceUID
        target.PatientIdentityRemoved = "YES"
        target.DeidentificationMethod = "Research allowlist gateway v1; pixel review required"
        output = BytesIO()
        target.save_as(output, enforce_file_format=True)
        return IntegrationResult("MANUAL_REVIEW_REQUIRED", data={
            "dicom_bytes": output.getvalue(), "uid_hashes": hashes,
            "removed_tags": [e.keyword or str(e.tag) for e in source if e.keyword not in RETAIN],
            "retained_tags": sorted(RETAIN & {e.keyword for e in source}),
            "uid_mapping_status": "HASH_ONLY", "pixel_data_checked": False,
            "burned_in_annotation_status": "NOT_VERIFIED", "ocr_status": "NOT_CONFIGURED",
            "manual_review_required": True, "deidentification_profile": "RESEARCH_ALLOWLIST",
            "profile_version": "1.0"})
    except Exception:
        return IntegrationResult("DEGRADED", "INVALID_DICOM")
