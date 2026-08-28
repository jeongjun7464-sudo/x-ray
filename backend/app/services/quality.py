from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class QualityResult:
    score: float
    contrast: float
    clipped_fraction: float
    reasons: tuple[str, ...]


def assess_image_quality(pixels: object) -> QualityResult:
    arr = np.asarray(pixels, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr.mean(axis=-1)
    if arr.max() > 1:
        arr /= 255.0
    contrast = float(np.std(arr))
    clipped = float(((arr <= 0.01) | (arr >= 0.99)).mean())
    reasons: list[str] = []
    if contrast < 0.035:
        reasons.append("LOW_CONTRAST")
    if clipped > 0.65:
        reasons.append("EXCESSIVE_CLIPPING")
    score = max(0.0, min(1.0, contrast / 0.18)) * max(0.0, 1.0 - clipped)
    return QualityResult(round(score, 4), round(contrast, 4), round(clipped, 4), tuple(reasons))
