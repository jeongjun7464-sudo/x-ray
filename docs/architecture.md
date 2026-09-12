# Architecture

## Phase 30 QMS 확장

기존 레코드 → QMS service/router → 규칙 기반 정합성 검사 → 독립 검토 게이트로 연결한다. 생성 전용 LangGraph와 검증 모듈은 분리되어 있고 생성기에 승인·배포 도구를 제공하지 않는다. ControlledDocumentVersion과 AuditChainEntry는 일반 ORM 변경을 거부한다. [세부 범위](phase30-qms-regulatory-traceability.md).

Phase 28은 모델 등록과 단일 활성 추론 binding 사이에 검증·독립 승인·Release Gate 계층을 둔다. 상세 설계는 `phase28-modelops-validation-deployment.md`에 있다.

운영 계층에는 `MonitoringSnapshot → DriftBaseline/DriftEvaluation → MonitoringAlert → ReleaseBlockDecision/OperationalCapa` 흐름이 추가된다. 모든 레코드는 모델·데이터 버전과 익명 기관 구분만 저장하며 환자 식별정보를 저장하지 않는다.

React/Vite 클라이언트가 FastAPI에 multipart 영상을 전송한다. 검증 계층은 확장자·MIME·시그니처·크기·실제 디코딩을 확인한다. DICOM 계층은 pydicom으로 픽셀을 추출하고 window/rescale/MONOCHROME 변환을 수행한다. `InferenceEngine` 인터페이스 뒤의 deterministic dummy 또는 DenseNet 계열 모델이 분류하며 정책 계층이 검토 여부를 정한다. SQLAlchemy는 영상 해시와 결과만 PostgreSQL/SQLite에 저장한다. 원본은 메모리/요청 생명주기 밖으로 보존하지 않는다.

`Browser → React → FastAPI → validation/DICOM → inference → review policy → SQLAlchemy → PostgreSQL|SQLite`

로컬 서명 세션과 역할 기반 권한 검사는 구현되어 있다. 실제 운영에서는 객체 저장소 격리, 악성 파일 검사, 조직 IdP/OIDC·MFA, 중앙 세션 폐기, KMS, 네트워크 분리와 운영 모니터링을 추가해야 한다.
