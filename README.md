# X-Ray Anatomical Region Classification & Routing System

X-ray 영상을 업로드하면 8개 해부학적 부위를 분류하고 신뢰도, 상위 3개 결과, 좌우·촬영 방향 및 검토 필요 사유를 보여주는 취업 포트폴리오용 풀스택 프로젝트입니다. **연구·교육용 보조 시스템이며 질병을 진단하거나 의료진의 판단을 대체하지 않습니다.**

## 해결하려는 문제와 주요 기능

촬영 부위가 잘못되거나 메타데이터가 불완전한 의료영상을 자동 정리·분석 파이프라인으로 연결합니다.

- 8개 부위 분류, 신뢰도와 상위 3개 결과
- pydicom 기반 window/rescale/MONOCHROME1·2 처리와 비식별 사본
- deterministic dummy 모드와 DenseNet121 학습 구조
- 불확실성·방향 미상·메타데이터 충돌 기반 human review
- 예측 이력/수정/통계 API 및 한국어 반응형 React UI
- SQLite 개발 fallback, PostgreSQL Docker 구성

## 아키텍처와 기술 스택

`React + TypeScript + Vite → FastAPI/Pydantic → validation/pydicom → InferenceEngine → review policy → SQLAlchemy → SQLite/PostgreSQL`

Python 3.11, FastAPI, PyTorch/torchvision, pydicom, SQLAlchemy, PostgreSQL, React, TypeScript, Vite, Docker Compose, pytest, Vitest, GitHub Actions를 사용합니다. 상세 내용은 [architecture](docs/architecture.md)를 참고하세요.

코드에 실제 연결된 기술과 적용 위치는 [실제 적용 기술 스택](docs/technology-stack.md)에 표로 정리했습니다. 파일 품질 분석, 구조화 JSON 로그, 요청 ID, CSP, 인메모리 속도 제한, Alembic 초기 migration, PyTorch Grad-CAM과 검토 결과 수정 UI가 포함됩니다.

## 로컬 실행

```bash
cp .env.example .env
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload
```

새 터미널에서 `cd frontend && npm install && npm run dev`를 실행합니다. UI는 `http://localhost:5173`, API 문서는 `http://localhost:8000/docs`입니다. 기본값은 SQLite와 `dummy-v1`입니다.

## Docker 실행

```bash
docker compose up --build
```

`http://localhost:8080`에서 UI, `http://localhost:8000/docs`에서 API를 엽니다. Docker Compose는 PostgreSQL을 사용합니다.

## 환경변수

`.env.example`을 복사합니다. 주요 값은 `DATABASE_URL`, `MAX_UPLOAD_MB`, `AUTO_CLASSIFY_MIN_CONFIDENCE`, `UNCERTAINTY_MARGIN`, `CORS_ORIGINS`, `DUMMY_MODE`, `MODEL_VERSION`, `VITE_API_URL`입니다. 비밀값은 커밋하지 마세요.

## 테스트와 빌드

```bash
cd backend && pytest -q
cd ../frontend && npm test && npm run build
```

## API 예시

```bash
curl -F "file=@synthetic-xray.png;type=image/png" http://localhost:8000/api/predictions
curl http://localhost:8000/api/predictions
curl -X PATCH -H "Content-Type: application/json" -d '{"corrected_region":"CHEST","comment":"검토 완료"}' http://localhost:8000/api/predictions/PREDICTION_ID/review
```

## 모델 학습과 데이터

실제 의료영상이나 개인정보는 저장소에 넣지 않습니다. 폴더 클래스 구조 또는 CSV manifest(`file_path, anatomical_region, laterality, view_position, patient_group_id, institution_id`)를 사용합니다. 동일 환자가 서로 다른 분할에 섞이면 누수 검사에서 실패합니다.

```bash
pip install -r ml/requirements.txt
PYTHONPATH=ml python ml/train.py --train train.csv --val val.csv --out ml/runs/v1
PYTHONPATH=ml python ml/evaluate.py --manifest test.csv --checkpoint ml/runs/v1/best.pt
```

자세한 내용: [data preparation](docs/data-preparation.md), [model training](docs/model-training.md).

## 개인정보 보호, 평가 및 제한사항

DB에는 SHA-256 해시, 형식/크기와 예측·검토 결과만 저장합니다. 직접식별정보와 원본 영상은 저장하지 않습니다. 업로드는 확장자, MIME, 시그니처, 크기, 실제 디코딩으로 검증합니다. [privacy & security](docs/privacy-security.md)

실제 가중치와 임상 데이터가 없으므로 Accuracy/F1을 주장하지 않습니다. dummy 결과는 제품 흐름 시연용입니다. 평가 코드는 Accuracy, Macro F1, 클래스별 Precision/Recall/F1, confusion matrix와 ECE를 지원합니다.

현재 제한사항은 실제 학습 가중치 부재, Grad-CAM API/UI 오버레이 연결 전 단계, 영상 기반 laterality/view 전용 모델 부재, 인증/RBAC 및 Redis 기반 분산 rate limit 미구현입니다. Grad-CAM 계산 모듈 자체는 구현되어 실제 체크포인트에 연결할 수 있습니다. 임상 도입 전 다기관 외부·전향 검증, calibration, subgroup/failure-mode 분석, human factors, 개인정보·보안 심사와 규제 검토가 필요합니다. [validation plan](docs/validation-plan.md)

화면 캡처는 합성 영상만 사용해 `docs/screenshots/`에 추가합니다. 향후 Grad-CAM, OOD/품질 모델, calibration, drift 모니터링, 인증/RBAC와 다기관 검증을 연결할 계획입니다. 포트폴리오 문구는 [portfolio description](docs/portfolio-description.md)에 있습니다.

