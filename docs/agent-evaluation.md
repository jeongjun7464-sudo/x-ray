# Agent 평가

Retrieval은 Hit@5, Recall@5, MRR, nDCG, 승인 문서 비율, 역할 위반, 중복 청크를 평가한다. Generation은 citation precision/recall, groundedness, unsupported claim, JSON schema, safety violation, refusal accuracy를 평가한다. Agent는 intent/tool accuracy, 권한 위반, 완료율, latency, fallback 성공률을 평가한다. 실제 평가 세트가 없으므로 현재 수치를 주장하지 않으며 합성 실행은 `SYNTHETIC_EVALUATION`으로만 기록한다.
