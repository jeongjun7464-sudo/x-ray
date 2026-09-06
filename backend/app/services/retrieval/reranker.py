def rerank(query,results):
    terms=set(query.lower().split())
    for item in results:item["rerank_score"]=item.get("rrf_score",0)+.001*len(terms&set(item.get("content","").lower().split()))
    return sorted(results,key=lambda x:x["rerank_score"],reverse=True)
