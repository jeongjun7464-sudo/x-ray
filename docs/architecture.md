# Architecture

React/Vite 클라이언트가 FastAPI에 multipart 영상을 전송한다. 검증 계층은 확장자·MIME·시그니처·크기·실제 디코딩을 확인한다. DICOM 계층은 pydicom으로 픽셀을 추출하고 window/rescale/MONOCHROME 변환을 수행한다. `InferenceEngine` 인터페이스 뒤의 deterministic dummy 또는 DenseNet 계열 모델이 분류하며 정책 계층이 검토 여부를 정한다. SQLAlchemy는 영상 해시와 결과만 PostgreSQL/SQLite에 저장한다. 원본은 메모리/요청 생명주기 밖으로 보존하지 않는다.

`Browser → React → FastAPI → validation/DICOM → inference → review policy → SQLAlchemy → PostgreSQL|SQLite`

실제 운영에서는 객체 저장소 격리, 악성 파일 검사, 인증·권한(RBAC), 감사 로그, KMS, 네트워크 분리, 모니터링을 별도 추가해야 한다.
