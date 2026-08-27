# Validation plan

1. 파일 검증: 정상 PNG/JPEG/DICOM, MIME 위조, 시그니처 불일치, 손상/무픽셀/압축 DICOM, 경계 크기.
2. 픽셀: MONOCHROME1/2, rescale, window, 8-bit 범위.
3. 모델: 출력 차원, CPU/CUDA 일관성, checkpoint, seed 재현성.
4. 데이터: 환자 누수, 기관 외부 검증, 클래스 불균형.
5. 정책: 신뢰도/마진/품질/메타데이터 충돌/UNKNOWN.
6. 임상 전: 대표성 있는 다기관 후향 검증, calibration, subgroup, reader study, 전향적 silent trial, 실패모드와 human factors 평가.

실제 임상 사용을 위해서는 해당 국가의 의료기기 규제 검토와 기관 승인이 별도로 필요하다.
