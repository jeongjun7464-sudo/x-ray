# Hybrid Retrieval

질문 정규화 후 기존 한국어 정규식 토큰 BM25와 Qdrant dense 검색을 수행하고 RRF로 합친다. 문서당 최대 두 청크, 최종 5개를 선택하며 승인·역할·기관·유효기간을 다시 검사한다. Qdrant 장애는 `LOCAL_FALLBACK`, 결과 없음은 `NO_EVIDENCE`다. BM25/vector 순위, RRF 점수와 선택 여부를 trace용 DB 이벤트에 저장한다.
