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

## Phase 21 의료기기 소프트웨어 연결

| 사용자 요구사항 | 소프트웨어 요구사항 | 위험/통제 | 설계·구현 | 테스트 | 결과/결함·CAPA |
|---|---|---|---|---|---|
| URS-XR-021 | SRS-XR-021 | RISK-XR-021: 비 X-ray 강제 분류 → 단계 중단 | DES-XR-021 `run_multistage` | TST-XR-021 | 자동시험; 실패 시 BUG-XR/CAPA-XR 연결 |
| URS-XR-022 | SRS-XR-022 | RISK-XR-022: 빈 탐지 모델을 AI로 오인 → NOT_AVAILABLE | DES-XR-022 detection/landmark interface | TST-XR-022 | 자동시험 |
| URS-XR-023 | SRS-XR-023 | RISK-XR-023: 검수 편향 → 독립 검수자 강제 | DES-XR-023 `LabelTask` | TST-XR-023 | 자동시험 |
| URS-XR-024 | SRS-XR-024 | RISK-XR-024: 계보 단절 → 해시·버전 기록 | DES-XR-024 `LineageEvent` | TST-XR-024 | 자동시험 |
| URS-XR-025 | SRS-XR-025 | RISK-XR-025: 미검증 기능 노출 → 플래그·감사 | DES-XR-025 `FeatureFlag` | TST-XR-025 | 자동시험 |
| URS-XR-026 | SRS-XR-026 | RISK-XR-026: 의료 데이터 브라우저 캐시 | DES-XR-026 `sw.js` API 제외 | TST-XR-026 | 빌드·정적검사 |
| URS-XR-027 | SRS-XR-027 | RISK-XR-027: 반복 결함 미추적 | DES-XR-027 `Defect`, `Capa` | TST-XR-027 | 자동시험 |
| URS-XR-028 | SRS-XR-028 | RISK-XR-028: 잘못된 모달리티 호출 | DES-XR-028 imaging hub adapter | TST-XR-028 | 자동시험 |

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
