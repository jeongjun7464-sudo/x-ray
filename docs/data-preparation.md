# Data preparation

폴더 구조 또는 CSV manifest를 지원한다. 동일 환자의 `patient_group_id`가 train/val/test에 동시에 존재하면 `assert_no_patient_leakage`가 실패한다. 분할은 반드시 환자 단위로 먼저 수행하고, 가능하면 기관 단위 외부 검증도 추가한다.

기관명·문자 마커·콜리메이션 테두리·장비 해상도·후처리 스타일은 병변/부위가 아닌 지름길 신호가 될 수 있다. 식별 문자를 제거하고 기관별 분포를 점검하며, 마커 가림 ablation과 외부기관 평가를 수행한다. 좌우 반전 증강은 laterality 학습과 충돌할 수 있으므로 목적에 맞게 제한한다.
