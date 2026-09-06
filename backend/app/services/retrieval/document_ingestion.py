import hashlib,re,uuid
from datetime import datetime,timezone
from pathlib import Path
from .embedding_client import EmbeddingClient
from .security import validate_document
ROOT=Path(__file__).resolve().parents[4];KNOWLEDGE=ROOT/"docs"/"knowledge"
REQUIRED={"document_id","title","document_type","version","approval_status","effective_date","allowed_roles","institution_id"}
def parse_document(path):
    text=path.read_text(encoding="utf-8");validate_document(text)
    if not text.startswith("---\n"):raise ValueError("FRONT_MATTER_REQUIRED")
    raw,content=text[4:].split("\n---\n",1);meta={}
    for line in raw.splitlines():
        if ":" in line:
            key,value=line.split(":",1);value=value.strip();meta[key.strip()]=[x.strip() for x in value.strip("[]").split(",")] if key.strip()=="allowed_roles" else value
    missing=REQUIRED-set(meta)
    if missing:raise ValueError("MISSING_METADATA:"+",".join(sorted(missing)))
    chunks=[]
    for index,part in enumerate(x for x in re.split(r"\n(?=##? )",content) if x.strip()):
        section=part.splitlines()[0].lstrip("# ")[:120];chunk_id=f'{meta["document_id"]}-{meta["version"]}-CH-{index+1:03d}';digest=hashlib.sha256(part.encode()).hexdigest()
        chunks.append(meta|{"chunk_id":chunk_id,"section":section,"content":part[:4000],"content_hash":digest,"source_path":str(path.relative_to(ROOT)).replace("\\","/"),"language":"ko","embedding_model":EmbeddingClient.model,"created_at":datetime.now(timezone.utc).isoformat(),"deleted":False})
    return meta,chunks
def load_documents():
    docs=[];errors=[]
    for path in sorted(KNOWLEDGE.glob("*.md")):
        try:_,chunks=parse_document(path);docs.extend(chunks)
        except Exception as exc:errors.append({"path":str(path),"error":str(exc)})
    return docs,errors
def qdrant_points(chunks):
    embed=EmbeddingClient();return [{"id":str(uuid.uuid5(uuid.NAMESPACE_URL,c["chunk_id"]+c["content_hash"])),"vector":embed.embed(c["content"]),"payload":c} for c in chunks]
