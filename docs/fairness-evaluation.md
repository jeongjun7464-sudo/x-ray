# 모델 공정성 평가

승인된 검증 사례가 제공될 때만 연령대, 성별, 장비, 기관, 촬영 방향, 품질 등급별 sensitivity, specificity, precision/recall, F1, FPR/FNR을 계산한다. score와 양·음성 표본이 모두 있으면 AUROC도 계산한다. 그룹 표본 수가 임계값보다 작으면 `INSUFFICIENT_DATA`, 검증 자료가 없으면 빈 그룹 결과를 반환한다. 차이는 검토 경고이며 개인의 민감 특성을 예측하지 않는다.
