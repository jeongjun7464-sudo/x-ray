from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from app.core.config import settings
from app.services.dicom_service import read_dicom, pixel_to_uint8

ALLOWED = {".png": {"image/png"}, ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}, ".dcm": {"application/dicom", "application/octet-stream"}}
@dataclass
class ValidatedImage:
    format: str; width: int; height: int; pixels: object; dicom: object | None = None
def validate_upload(filename: str, content_type: str, data: bytes) -> ValidatedImage:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED: raise ValueError("지원하지 않는 확장자입니다.")
    if content_type not in ALLOWED[ext]: raise ValueError("파일 확장자와 MIME 유형이 일치하지 않습니다.")
    if len(data) > settings.max_upload_mb*1024*1024: raise ValueError("파일 크기 제한을 초과했습니다.")
    if ext == ".dcm":
        ds = read_dicom(data); pixels = pixel_to_uint8(ds); h, w = pixels.shape[-2:]
        result = ValidatedImage("DICOM", w, h, pixels, ds)
    else:
        signatures = ext == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n") or ext in {".jpg", ".jpeg"} and data.startswith(b"\xff\xd8\xff")
        if not signatures: raise ValueError("파일 시그니처가 형식과 일치하지 않습니다.")
        try:
            image = Image.open(BytesIO(data)); image.verify(); image = Image.open(BytesIO(data)).convert("L")
        except (UnidentifiedImageError, OSError) as exc: raise ValueError("손상되었거나 디코딩할 수 없는 이미지입니다.") from exc
        result = ValidatedImage(ext[1:].upper(), image.width, image.height, image)
    if min(result.width, result.height) < settings.min_image_dimension or max(result.width, result.height) > settings.max_image_dimension:
        raise ValueError("비정상적인 이미지 크기입니다.")
    return result
