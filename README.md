# X-Ray Anatomical Region Classification & Routing System

## X-ray AI 구축 및 분석 지원 확장

새 `/api/v1/xray` 흐름은 PNG/JPG/DICOM 검증 → 메모리 내 비식별 처리 → 품질·부위 분류 → 10개 이상 의심 소견 multi-label 추론 → 불확실성/OOD → 의료진 검토 → 익명 PDF를 통합합니다. 기존 API는 그대로 유지됩니다.

- 실제 모델: 승인 체크포인트, 체크포인트 해시와 검증 자료가 구성된 경우에만 사용하며 실제 Grad-CAM만 제공합니다.
- 기본 모델: `dummy-finding-v1`은 파일 SHA-256 기반 재현용 DUMMY이며 임상 성능을 의미하지 않고 히트맵을 제공하지 않습니다.
- PACS/Orthanc, 운영 인증, 실제 소견 체크포인트: `NOT_CONFIGURED`.

주요 API는 `POST /api/v1/xray/analyze`, `POST /api/v1/xray/analyze-batch`, `GET /api/v1/xray/analyses/{id}`, `/heatmap`, `/report`, `GET /api/v1/xray/worklist`, `PATCH /api/v1/xray/analyses/{id}/review`입니다.

검증 결과: 백엔드·ML **39 passed**, 프론트엔드 **4 passed**, TypeScript/Vite 빌드 성공. 현재 환경에는 Docker CLI가 없어 `docker compose config`는 실행하지 못했습니다.

이 결과는 연구·교육용 분석 지원 정보이며 의료진의 진단이나 치료 결정을 대체하지 않습니다. 포트폴리오에서는 DICOM 보안, 다중 라벨 ML 계약, Human-in-the-loop, 모델 계보, 감사 로그와 책임 있는 AI를 강조합니다.

> Phase 23 adds AI literacy, versioned consent, measured latency, model/dataset cards, misclassification reporting, Human-in-the-loop controls and a responsible AI risk dashboard. The bundled model remains explicitly **DEMO / DUMMY** and is not for diagnosis or treatment decisions.

## 공동 개발

`jeongjun7464-sudo`와 `junhaj27-jpg` 모두 동일한 코드베이스에서 브랜치와 Pull Request 방식으로 개발할 수 있습니다. 계정별 로컬 Git 작성자 설정, Collaborator/Fork 방식과 병합 전 검증 절차는 [CONTRIBUTING.md](CONTRIBUTING.md)를 따릅니다. 코드 소유권 리뷰 요청은 [.github/CODEOWNERS](.github/CODEOWNERS)에 두 계정을 등록했습니다.

X-ray/DICOM 영상을 해부학적 촬영 부위로 분류하고, 영상 품질과 메타데이터를 교차검증한 뒤 적절한 분석 또는 검토 대기열로 연결하는 취업 포트폴리오용 풀스택 프로젝트입니다.

> **연구·교육 및 시스템 통합 검증용입니다.** 질병을 진단하거나 촬영을 재지시하지 않으며 의료진의 판단을 대체하지 않습니다. 기본 `dummy-v1` 결과는 워크플로 시연용으로 실제 의료 AI 성능을 의미하지 않습니다.

## 구현된 전체 흐름

```text
합성/익명 영상 업로드
→ 파일·DICOM 검증 및 비식별 미리보기
→ 영상 품질/OOD 검사
→ 촬영 부위 분류와 메타데이터 교차검증
→ 규칙 기반 파이프라인 또는 검토 대기열 라우팅
→ 검토자 수정·감사 로그·능동학습 후보 등록
→ 익명 PDF / 실험용 DICOM SR / 로컬 FHIR Bundle 내보내기
```

## 주요 기능

### 분류·품질·검토

- 8개 해부학적 부위, 신뢰도 및 상위 3개 결과
- pydicom window/rescale와 `MONOCHROME1`·`MONOCHROME2` 처리
- 밝기, 대비, 흐림, 빈 영상, 해상도 기반 `PASS/WARNING/REJECT` 품질 판정
- 신뢰도, predictive entropy, DICOM Modality 기반 OOD 탐지
- DICOM 메타데이터와 AI 결과 충돌 검사
- 부위별 안전한 분석 라우팅과 낮은 신뢰도 자동 검토
- 우선순위 기반 워크리스트, 검토 수정, 감사 로그
- 익명 능동학습 CSV와 개인정보 없는 PDF 결과 보고서
- DenseNet121, EfficientNetV2, ConvNeXt, ONNX 형식의 명시적 모의 비교 API

### 의료기관 연동 구조

- DICOM UID 해시 기반 검사·시리즈·인스턴스 그룹화와 중복 SOP 차단
- AP/LATERAL 등 동일 검사의 다중 촬영 방향 통합
- DB 관리형 부위별 촬영 프로토콜과 완전성 검사
- 생성 근거가 포함된 검색 태그와 검토자 수정
- 관리자 입력형 SNOMED CT, RadLex, DICOM Body Part 매핑 구조
- `UNVERIFIED/PARTIAL`로 표시되는 연구용 DICOM SR
- FHIR R4 ImagingStudy, DiagnosticReport, Observation, DocumentReference, AuditEvent, Provenance 예제 Bundle
- 우선순위·활성화·버전이 저장되는 규칙 기반 라우팅
- HMAC 서명과 감사 로그가 연결된 로컬 웹훅 대기열
- ZIP 경로 조작, 심볼릭 링크, 중첩 압축, 파일 수·크기·압축률 검사
- 관리자 권한으로 보호되는 서비스 상태 API와 React 관리 화면

### LangGraph 의료영상 업무지원 Agent

- 실제 `StateGraph` 기반 의도 분류→문서 검색→허용 도구→답변→근거 검증 흐름
- API 키 없이 실행되는 deterministic dummy Agent
- 예측·모델·시스템 상태·감사·시험·추적성에 연결된 읽기 도구 7개
- BM25 유사 키워드 점수와 token-vector 검색을 RRF로 결합한 로컬 하이브리드 검색
- 문서 ID·버전·섹션·시스템 도구가 표시되는 근거 기반 답변
- 개인정보 마스킹, prompt injection 차단, 도구 allowlist와 역할 검사
- 변경 도구 제안과 별도 사용자 확인 API 분리
- LangGraph 노드 실행시간·도구·검색·안전 결과 trace 및 사용자 피드백 저장
- React 업무지원 대화 화면과 합성 Agent 평가 데이터셋

### 합성 데이터 데모

- 정상 DICOM, MONOCHROME1/2, 개인정보 태그, 픽셀 없음, 손상 파일
- 잘못된 Modality, 메타데이터 충돌, 대형 영상 변형
- 합성 DICOM 생성부터 업로드·분류·검토·보고서까지 시연
- 합성 데이터는 시스템 기능 검증 전용이며 모델 성능 평가에는 사용하지 않음

## 기술 스택

| 영역 | 실제 연결 기술 |
|---|---|
| Frontend | React, TypeScript, Vite, Vitest |
| API | FastAPI, Pydantic, multipart upload |
| Medical imaging | pydicom, Pillow, NumPy |
| ML structure | PyTorch, torchvision, DenseNet121, Grad-CAM module |
| Database | SQLAlchemy, Alembic, SQLite 개발 모드, PostgreSQL Docker 모드 |
| Security | 파일 시그니처 검증, SHA-256 익명 해시, 역할 헤더 검사, HMAC, CSP, rate limit |
| Delivery | Docker Compose, nginx, GitHub Actions |

상세 내용은 [실제 적용 기술 스택](docs/technology-stack.md)과 [아키텍처](docs/architecture.md)를 참고하세요.

## 빠른 실행

### 로컬 개발

```bash
cp .env.example .env
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload
```

새 터미널에서 프론트엔드를 실행합니다.

```bash
cd frontend
npm install
npm run dev
```

- UI: `http://localhost:5173`
- Swagger API: `http://localhost:8000/docs`
- 기본 DB/모델: SQLite / `dummy-v1`

### Docker Compose

```bash
docker compose up --build
```

- UI: `http://localhost:8080`
- API 문서: `http://localhost:8000/docs`
- Docker DB: PostgreSQL 16

## 주요 API

| API | 설명 |
|---|---|
| `POST /api/predictions` | 단일 영상 검증·분류·품질/OOD 평가 |
| `PATCH /api/predictions/{id}/review` | 검토 결과와 의견 저장 |
| `GET /api/worklist` | 사유·우선순위 검토 목록 |
| `GET /api/demo/synthetic-dicom` | 합성 DICOM 생성 |
| `POST /api/studies/group` | 복수 DICOM 검사·시리즈 그룹화 |
| `GET/PUT /api/admin/protocols` | 촬영 프로토콜 조회·관리 |
| `GET/PUT /api/admin/code-mappings` | 표준 코드 매핑 조회·관리 |
| `POST /api/admin/routing-rules` | 버전 관리형 라우팅 규칙 생성 |
| `POST /api/routing/evaluate` | 규칙 기반 목적지 평가 |
| `POST /api/batches/inspect` | 안전한 ZIP 배치 사전검사 |
| `GET /api/predictions/{id}/fhir` | 로컬 FHIR 예제 Bundle |
| `GET /api/predictions/{id}/dicom-sr` | 실험용 DICOM SR |
| `GET /api/predictions/{id}/report.pdf` | 익명 PDF 보고서 |
| `GET /api/admin/dashboard` | 관리자 서비스 상태 |
| `POST /api/agent/chat` | LangGraph 업무지원 Agent 실행 |
| `GET /api/agent/runs` | 권한 보호된 익명 Agent trace 조회 |
| `POST /api/agent/actions` | 변경 도구 실행 전 제안 생성 |
| `POST /api/agent/actions/{id}/confirm` | 사용자 확인 후 승인된 변경 수행 |

관리 API 데모 권한은 `X-Role: ADMIN`, 태그 수정은 `ADMIN` 또는 `REVIEWER` 헤더를 사용합니다. 이는 포트폴리오용 최소 RBAC 검사이며 운영 환경에서는 OIDC/OAuth2 인증으로 교체해야 합니다.

```bash
curl -F "file=@synthetic-xray.png;type=image/png" http://localhost:8000/api/predictions
curl -H "X-Role: ADMIN" http://localhost:8000/api/admin/dashboard
curl -F "files=@ap.dcm;type=application/dicom" -F "files=@lateral.dcm;type=application/dicom" http://localhost:8000/api/studies/group
```

## 테스트

```bash
PYTHONPATH=backend:ml pytest backend/tests ml/tests -q
cd frontend
npm test
npm run build
```

현재 검증 기준:

- 백엔드·ML: **28 tests passed**
- 프론트엔드: **2 tests passed**
- TypeScript 검사 및 Vite 프로덕션 빌드 통과

요구사항과 위험, 구현 파일, API, 테스트 연결은 [추적성 매트릭스](docs/traceability-matrix.md)에 기록합니다.

## 모델 학습과 데이터 준비

실제 의료영상, 환자 개인정보 또는 공개 데이터셋 원본을 저장소에 포함하지 않습니다. 폴더 클래스 구조 또는 CSV manifest(`file_path, anatomical_region, laterality, view_position, patient_group_id, institution_id`)를 사용하며 환자 단위 분할로 데이터 누수를 검사합니다.

```bash
pip install -r ml/requirements.txt
PYTHONPATH=ml python ml/train.py --train train.csv --val val.csv --out ml/runs/v1
PYTHONPATH=ml python ml/evaluate.py --manifest test.csv --checkpoint ml/runs/v1/best.pt
```

관련 문서: [데이터 준비](docs/data-preparation.md), [모델 학습](docs/model-training.md), [검증 계획](docs/validation-plan.md).

## 개인정보 보호와 제한사항

- 원본 영상과 직접식별정보는 DB에 저장하지 않습니다.
- UID와 AccessionNumber는 검색 가능한 익명 해시로 저장합니다.
- FHIR 예제는 로컬 합성·익명 데이터만 생성하며 외부 병원으로 전송하지 않습니다.
- DICOM SR은 임상적으로 검증된 진단 보고서가 아닙니다.
- 임의의 SNOMED CT 또는 RadLex 코드를 생성하지 않습니다.
- 실제 가중치와 임상 검증 데이터가 없어 Accuracy/F1 또는 진단 성능을 주장하지 않습니다.
- 실제 웹훅 전송, Redis/Celery worker, Orthanc, MinIO, MLflow, 운영 백업·복구는 연결되지 않았습니다.
- 헤더 기반 역할 검사는 데모 수준이며 완전한 사용자 인증 체계가 아닙니다.
- Grad-CAM 계산 모듈은 있으나 dummy 모델 UI에서는 실제 히트맵을 제공하지 않습니다.

Phase 20 범위는 [의료기관 연동 구현 현황](docs/phase20-implementation-status.md), Phase 21은 [AI 고도화 및 검증 구현 현황](docs/phase21-implementation-status.md), Agent의 실제·부분·미구현 범위는 [Phase 22 Agent 현황](docs/phase22-agent-status.md), 최신 시험 결과는 [자동 검증 요약](docs/validation-summary.md)에서 확인할 수 있습니다.

## 저장소 원칙

- 라이선스 동의나 로그인을 우회하지 않습니다.
- 실제 의료영상, 개인정보, 비밀키와 대용량 모델 아티팩트를 커밋하지 않습니다.
- 설치만 한 기술을 실제 사용 기술로 표시하지 않습니다.
- 검증되지 않은 모델을 자동으로 운영 모델로 승격하지 않습니다.
- 구현하지 않은 기능은 완료로 표시하지 않고 제한사항과 이유를 공개합니다.
