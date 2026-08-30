# 추적성 매트릭스

| 요구사항 ID | 위험 ID | 구현 파일 | API | 테스트 ID | 최근 결과 |
|---|---|---|---|---|---|
| DIF-01 자동 라우팅 | R-ROUTE-01 | `services/differentiators.py` | `POST /api/predictions` | `test_synthetic_dicom_and_ood` | PASS |
| DIF-02 품질 검사 | R-QUALITY-01 | `services/quality.py`, `services/differentiators.py` | `POST /api/predictions` | `test_quality_flags_flat_image` | PASS |
| DIF-03 OOD | R-OOD-01 | `services/differentiators.py` | `POST /api/predictions` | `test_synthetic_dicom_and_ood` | PASS |
| DIF-04 메타 교차검증 | R-META-01 | `dicom_service.py`, `differentiators.py` | `POST /api/predictions` | `test_synthetic_dicom_and_ood` | PASS |
| DIF-05 능동학습 | R-PRIV-01 | `main.py`, `models.py` | `GET /api/active-learning/export.csv` | `test_review_update` | PASS |
| DIF-06 모델 비교 | R-MODEL-01 | `differentiators.py` | `POST /api/model-comparison` | `test_model_comparison_is_explicitly_mock` | PASS |
| DIF-08 합성 DICOM | R-TEST-01 | `synthetic_dicom.py` | `GET /api/demo/synthetic-dicom` | `test_synthetic_dicom_and_ood` | PASS |
| DIF-09 워크리스트 | R-DELAY-01 | `main.py` | `GET /api/worklist` | API 회귀 테스트 | PASS |
| DIF-12 익명 보고서 | R-PRIV-02 | `main.py` | `GET /api/predictions/{id}/report.pdf` | `test_review_update` | PASS |

CSV 버전은 `docs/traceability-matrix.csv`이며 테스트 실행 후 결과 열을 갱신한다. 아직 완성되지 않은 데이터 편향 분석과 실제 승인 모델 병렬 비교는 이 표에서 PASS로 표시하지 않는다.
# Phase 20 추가 추적성

| 요구사항 ID | 위험 ID | 구현 파일/API | 테스트 ID | 상태 |
|---|---|---|---|---|
| REQ-20-01 | RISK-DUPLICATE-PHI | `models.py`, `institution.py`, `POST /api/studies/group` | TEST-20-GROUP | PASS |
| REQ-20-02 | RISK-PROTOCOL-MISUSE | `ProtocolDefinition`, `GET/PUT /api/admin/protocols` | TEST-20-PROTOCOL | PASS |
| REQ-20-04 | RISK-CODE-FABRICATION | `CodeMapping`, `GET/PUT /api/admin/code-mappings` | TEST-20-RBAC | PASS |
| REQ-20-05/06 | RISK-CLINICAL-MISREPRESENTATION | `experimental_sr`, `fhir_bundle` | TEST-20-EXPORT | PASS |
| REQ-20-08 | RISK-WRONG-ROUTE | `RoutingRule`, `POST /api/routing/evaluate` | TEST-20-RULE | PASS |
| REQ-20-09 | RISK-ZIP-BOMB | `inspect_zip`, `POST /api/batches/inspect` | TEST-20-ZIP | PASS |
| REQ-20-16 | RISK-UNCERTAINTY | `uncertainty`, `POST /api/uncertainty` | TEST-20-UNCERTAINTY | PASS |
| REQ-20-22 | RISK-UNAUTHORIZED-ADMIN | `GET /api/admin/dashboard`, `App.tsx` | TEST-20-RBAC | PASS |
