import math,re
from collections import Counter
def tokens(text):return re.findall(r"[가-힣A-Za-z0-9_-]{2,}",text.lower())
class BM25Store:
    def search(self,query,documents,limit=8):
        q=tokens(query);df=Counter(t for t in set(q) for d in documents if t in set(tokens(d["content"])))
        ranked=[]
        for d in documents:
            counts=Counter(tokens(d["content"]));score=sum(counts[t]*math.log((len(documents)+1)/(df[t]+1)+1) for t in q)
            if score>0:ranked.append((score,d))
        return [d|{"bm25_score":score} for score,d in sorted(ranked,key=lambda x:x[0],reverse=True)[:limit]]
