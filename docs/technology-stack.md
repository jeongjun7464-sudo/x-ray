# 실제 적용 기술 스택

이 문서는 저장소 코드에 실제 연결된 기술만 기록한다. 단순 후보 기술은 아래의 "운영 확장"에 구분한다.

| 영역 | 기술 | 실제 적용 위치 |
|---|---|---|
| API | FastAPI, Pydantic | 업로드, 예측, 이력, 검토, 통계, OpenAPI |
| 영상 | pydicom, Pillow, NumPy | DICOM decode, window/rescale, MONOCHROME, PNG/JPEG 검증, 품질 점수 |
| ML | PyTorch, torchvision DenseNet121 | 학습·평가·추론, checkpoint, CPU/CUDA, Grad-CAM |
| 데이터 | pandas, patient-group split | 폴더/CSV Dataset, 환자 누수 검사 |
| 평가 | scikit-learn | Accuracy, Macro F1, 클래스별 P/R/F1, confusion matrix, ECE |
| DB | SQLAlchemy, Alembic | SQLite/PostgreSQL 모델과 초기 migration |
| 프론트 | React 19, TypeScript, Vite, Lucide | 반응형 대시보드, 업로드, 결과, 검토 수정, 통계 |
| 보안 | 내용 기반 파일 검사, SHA-256, CORS, CSP | PHI 비저장, 요청 ID, 보안 헤더, 인메모리 rate limit |
| 운영 | Docker, Compose, Nginx, Uvicorn | PostgreSQL 포함 로컬 컨테이너 실행 |
| 품질 | pytest, Vitest, Testing Library | API/DICOM/품질/ML/Grad-CAM/UI 테스트 |
| CI | GitHub Actions, Ruff, pip-audit, npm audit, Gitleaks | 테스트·빌드·lint·취약점·비밀 검사 |

## 데이터 파이프라인

1. 확장자, MIME, 파일 시그니처, 크기, 해상도와 실제 decode를 검증한다.
2. DICOM이면 rescale slope/intercept와 window를 적용하고 MONOCHROME1을 반전한다.
3. 대비와 clipping 비율을 계산해 저품질 영상을 검토 대상으로 보낸다.
4. `InferenceEngine`을 통해 deterministic dummy 또는 실제 PyTorch 모델을 호출한다.
5. 신뢰도, 상위 확률 차이, 방향 미상, 메타데이터 충돌, 품질을 검토 정책에 결합한다.
6. 원본과 직접식별정보 없이 해시와 결과만 저장하고 검토자가 정답을 수정한다.

## 운영 확장 시 필요한 기술

Redis 기반 분산 rate limit/작업 큐, S3 호환 격리 저장소, OIDC/RBAC, OpenTelemetry, Prometheus/Grafana, Sentry, Kubernetes, 모델 레지스트리(MLflow), 데이터 버전 관리(DVC)는 실제 다중 인스턴스 운영 단계에서 도입할 수 있다. 현재 저장소에는 연결되지 않았으므로 "사용 기술"로 주장하지 않는다.
