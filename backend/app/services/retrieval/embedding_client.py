import hashlib,math,re
from app.core.config import settings
class EmbeddingClient:
    """Deterministic local hashing embedding; contains no patient data persistence."""
    model=settings.embedding_model
    def embed(self,text):
        vector=[0.0]*settings.qdrant_vector_size
        for token in re.findall(r"[가-힣A-Za-z0-9_-]{2,}",text.lower()):
            h=int(hashlib.sha256(token.encode()).hexdigest(),16);vector[h%len(vector)]+=1 if (h>>8)&1 else -1
        norm=math.sqrt(sum(x*x for x in vector)) or 1;return [x/norm for x in vector]
