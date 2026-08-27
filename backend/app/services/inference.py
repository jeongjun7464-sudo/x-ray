import hashlib, random
from abc import ABC, abstractmethod
from app.core.constants import REGIONS

class InferenceEngine(ABC):
    @abstractmethod
    def predict(self, image, file_hash: str) -> list[dict]: ...
class DummyInferenceEngine(InferenceEngine):
    version = "dummy-v1"
    def predict(self, image, file_hash: str) -> list[dict]:
        rng = random.Random(int(file_hash[:16], 16)); raw = [rng.random()**2 for _ in REGIONS]; total = sum(raw)
        scores = sorted(zip(REGIONS, (x/total for x in raw)), key=lambda x: x[1], reverse=True)
        return [{"class": c, "display_name": REGIONS[c], "confidence": round(p, 4)} for c,p in scores[:3]]
def file_digest(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
engine: InferenceEngine = DummyInferenceEngine()
