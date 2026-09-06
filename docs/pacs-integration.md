# PACS 연동 설계

`app.services.pacs`는 Orthanc REST와 DICOMweb QIDO-RS(검색), WADO-RS(조회), STOW-RS(저장) 계약을 분리한다. 기본 상태는 `NOT_CONFIGURED`이며 외부 전송은 `DISABLED_BY_DEFAULT`이다. 자격증명과 승인된 엔드포인트가 없는 환경에서는 네트워크 호출을 하지 않는다.

현재 검증 범위는 합성 DICOM의 로컬 import, UID 익명 해시, Study 그룹화와 연동 상태 API다. 실제 Orthanc/PACS 인증, TLS, 재시도, 전송 감사와 상호운용성 시험은 미구현이며 완료로 주장하지 않는다.
