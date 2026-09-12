# Phase 29 의료기관 연동 — 개발 중

현재 상태는 PARTIAL이다. Phase 28 WIP 브랜치의 후속 브랜치이며 main 병합은 수행하지 않았다.

## 구현 및 검증된 범위

- 공통 HTTP 어댑터: 제한된 응답 크기, timeout, 인증 오류, TLS 오류 분류, redirect 차단, 비밀값 제외 응답.
- Orthanc: `/system`, `/tools/find` Study/Series 검색, 특정 instance 가져오기, DICOM 저장 HTTP 계약.
- DICOMweb: QIDO 검색 결과의 UID 해시 반환, 단일 application/dicom WADO 응답, multipart STOW 요청과 부분 실패 구분.
- 비식별화 Gateway: 새 allowlist dataset 구성, 원본 식별 태그·private tag·nested sequence 제외, UID 재발급 및 원본 UID SHA-256 해시만 반환.
- FHIR 연구용 collection: Patient, Device, ImagingStudy, Observation, DiagnosticReport, DocumentReference, Provenance, AuditEvent 연결. 예측은 preliminary로 유지.
- 로컬 FHIR 검사: 연결되지 않은 reference, 중복 fullUrl, 일부 개인정보 필드, 연구용 상태 검사. 전체 표준 검증은 NOT_VERIFIED이며 전송은 차단.
- httpx MockTransport와 합성 DICOM으로 어댑터 계약을 테스트한다. 실제 병원 PACS/FHIR 연결은 NOT_CONFIGURED.
- INT-001~018 정합성 규칙: 증거가 없으면 NOT_VERIFIABLE로 표시하고 외부 전송을 차단한다. confirm API는 정합성 결과와 감사 이벤트를 저장한다.
- 전송 실패 상태 처리: 수신자의 멱등성 보장이 확인된 재시도 가능 오류만 제한된 지수 백오프 시각을 기록한다. 불확실한 전송은 수동 검토, 인증 오류 및 재시도 소진은 격리한다. 이는 상태 처리 로직이며 실행 워커가 아니다.

## 아직 구현하지 않은 범위

실제 전송 워커·지수 백오프 스케줄러·격리 복구 실행, 선택적 Orthanc Compose 프로필, DICOM SR 추가 정보 연결과 hash 기반 import는 남아 있다. DICOMweb 경로는 현재 표준 /studies 기반으로 고정되며 사용자 정의 경로 설정은 아직 적용되지 않는다. 어댑터의 confirmed 인자는 서비스 권한 검사를 대체하지 않는다. 새 API의 confirm은 검증기 미연결로 전송을 차단하고 감사·보안 이벤트를 저장한다.

## 추가 연결한 서비스 계층

InstitutionConnection, ExternalTransferJob, ExternalTransferEvent, DicomUidMapping, FhirExportRecord와 0015_integrations migration을 추가했다. 사용자·리소스 기관 매핑은 서버 환경의 INTEGRATION_PRINCIPAL_INSTITUTIONS / INTEGRATION_RESOURCE_INSTITUTIONS JSON 설정으로 관리하며 미매핑 리소스는 접근을 거부한다. QIDO 검색에는 INTEGRATION_CONNECTION_INSTITUTION_ID 일치도 요구한다. 요청 X-Role 또는 기관 헤더는 새 API 권한 근거로 사용하지 않는다.

연동센터 화면에서 상태 확인, 합성 DX 검색, 익명 분석 FHIR 미리보기, 전송 제안 및 명시적 확인 대화상자를 사용한다. 확인 성공을 전송 성공으로 표시하지 않는다. 기관 단위 멱등 키는 DB unique constraint로 보호한다. 자유 입력 사유는 원문 대신 SHA-256으로 감사 이벤트에 기록한다.

연결 API: GET /api/v1/integrations/capabilities, POST /api/v1/integrations/health-check, GET /api/v1/integrations/connections, POST /api/v1/dicomweb/studies/search, GET /api/v1/xray/analyses/{id}/fhir, POST /api/v1/xray/analyses/{id}/fhir/validate, GET /api/v1/fhir/exports, POST /api/v1/external-transfers/proposals, GET /api/v1/external-transfers, GET /api/v1/external-transfers/{id}, POST .../confirm, POST .../cancel, POST .../retry. retry는 워커 미연결 사유를 반환한다. 기존 integrations/status는 호환용 미설정 상태 계약을 유지한다.

WADO multipart 응답은 현재 지원하지 않고 오류로 처리한다. QIDO UID 해시는 원본 UID를 복원하지 않으므로 hash 기반 import에는 추가 승인 매핑이 필요하다. 본 단계는 자동 수집 또는 실제 환자 데이터 전송을 수행하지 않았다.

## 개인정보와 UID 정책

픽셀의 burned-in text와 OCR은 검사하지 못하므로 항상 MANUAL_REVIEW_REQUIRED이며 원본 파일의 장기 저장은 수행하지 않는다. 태그 제거만으로 완전 익명화라고 주장하지 않는다. 현재 SHA-256에는 salt가 없으므로 동일 UID의 연계 및 사전 대입 가능성이 있다. 운영 적용 시 기관별 관리 키를 사용한 HMAC과 키 회전 정책을 먼저 구현해야 한다.

## 시험 실행

2026-09-11 로컬 회귀 검증: backend/tests 및 ml/tests **97 passed**, FastAPI startup on_event 사용 중단 예정 경고 2개. 프론트엔드 **12 files / 27 tests passed**, TypeScript `tsc -b` 통과. 이는 합성 데이터·모의 HTTP 및 로컬 환경의 결과이며 실제 PACS, FHIR 서버, PostgreSQL, 운영 배포 검증 결과가 아니다.

저장소 루트에서 PYTHONPATH에 backend와 ml을 설정하고 `python -m pytest backend/tests/test_phase29_adapters.py -q`를 실행한다. 테스트는 실제 외부 서버 없이 MockTransport를 사용한다. 개인 식별정보와 체크포인트는 저장소에 추가하지 않는다.

FHIR 설계 참고: [HL7 R4 Bundle](https://hl7.org/fhir/R4/bundle.html), [HL7 R4 DiagnosticReport](https://hl7.org/fhir/R4/diagnosticreport.html). 로컬 검사 통과는 FHIR 표준 적합성, 규제기관 승인 또는 임상 운영 승인을 의미하지 않는다.
