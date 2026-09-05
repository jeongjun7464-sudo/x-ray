# 현재 상태 분석

## 구현 상태

- 구현 완료: FastAPI 업로드·분류, DICOM 판독·비식별 처리, 품질/OOD·메타데이터 교차검증, 라우팅, 검토·감사·보고서, 합성 DICOM, 책임 있는 AI/Agent, React UI, PyTorch 부위 모델 구조.
- 부분 구현: 실제 모델 어댑터와 Grad-CAM 코드는 있으나 승인 체크포인트가 없어 운영 기본값은 결정론적 DUMMY이다. FHIR/DICOM SR은 로컬 연구 예제이며 외부 전송은 하지 않는다.
- 미구현/NOT_CONFIGURED: 실제 소견 체크포인트, PACS/Orthanc, 운영 OIDC, GPU 성능 검증, 임상 성능 검증.

## 기존 구조

- API: `/api/predictions`, `/api/worklist`, `/api/model-comparison`, `/api/studies/*`, `/api/admin/*`, `/api/agent/*`, `/api/ai-literacy/*`.
- DB: Prediction, AuditEvent, Study/Instance, Protocol/Mapping/Rule, Pipeline/Label/Lineage, Defect/CAPA, Agent, Consent/Latency/Report/Risk.
- ML: `ml/xray_classifier`의 DenseNet 구조·학습·평가·Grad-CAM, `backend/app/services/inference.py`의 동일 해시 재현 DUMMY.
- React: 단일 `App.tsx` 내 업로드, 결과, 검토, 통계, 관리자, Agent/AI 리터러시 화면과 Vitest.
- 분석 전 테스트: 백엔드·ML 34개, 프론트엔드 3개, Vite 빌드 통과.

## 이번 확장 지점과 충돌 위험

- 추가 파일: `ml/xray_findings`, 통합 API/DB 모델과 Alembic 0007, 통합 분석 UI, 신규 테스트·문서.
- 기존 `/api/predictions`는 변경하지 않고 `/api/v1/xray/*`로 분리해 호환성을 유지한다.
- SQLite `create_all` 개발 모드와 Alembic 운영 마이그레이션의 차이, 단일 `App.tsx` 규모, 실제/더미 모델 설정 불일치가 주요 위험이다.
- 원본 픽셀은 DB에 저장하지 않으며 SHA-256, 구조화 결과, 모델 버전과 검토 이력만 저장한다.
