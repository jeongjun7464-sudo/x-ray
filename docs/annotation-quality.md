# 라벨 품질관리

LABELER/RADIOLOGIST의 1차 판독, 다른 RADIOLOGIST의 독립 2차 판독, 불일치 탐지, ADJUDICATOR 합의 판독과 최종 승인을 분리한다. 모든 변경 전후 이력을 보존하며 `APPROVED` 전에는 `training_eligible=false`다. 일치도 API는 부위와 소견의 단순 일치율 및 표본 수를 반환한다. 임상 진단 일치도나 Cohen's kappa로 오인해서는 안 된다.
