# 추적성 매트릭스

## Phase 30 추적성

QMS DB에는 source/target 타입·ID·버전·코드 해시를 저장하고 양방향으로 조회한다. 존재하지 않는 대상은 등록 거부하며 사후 삭제·버전/콘텐츠 변경은 orphan/mismatch로 탐지한다. `/api/v1/qms/traceability-export`로 현재 링크의 CSV를 받는다. 기존 표의 PASS는 이전 실행 기록이며 Phase 30 전체 완료를 뜻하지 않는다.

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

## Phase 22 Agent 추적성

| 사용자 요구사항 | 위험 | 구현 | 테스트 | 상태 |
|---|---|---|---|---|
| URS-XR-029 Agent 조회 | RISK-XR-029 임의 DB 접근 | `medical_agent.py` allowlist | TST-XR-029 | COMPLETE |
| URS-XR-030 근거 답변 | RISK-XR-030 환각 | HybridRetriever·verify node | TST-XR-030 | COMPLETE |
| URS-XR-031 개인정보 | RISK-XR-031 PHI 노출 | `mask_sensitive` | TST-XR-031 | COMPLETE |
| URS-XR-032 Prompt injection | RISK-XR-032 지시 탈취 | safety flag·도구 차단 | TST-XR-032 | COMPLETE |
| URS-XR-033 변경 확인 | RISK-XR-033 무단 변경 | proposal→confirm API | TST-XR-033 | COMPLETE |
| URS-XR-034 Agent trace | RISK-XR-034 감사 불가 | `AgentRun`·AuditEvent | TST-XR-034 | COMPLETE |

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
| AUTH-REQ-01 | R-AUTH-BYPASS | `core/auth.py`, `main.py`, `POST /api/auth/demo-token` | TEST-AUTH-SIGNED-SESSION | PASS |
| AUTH-REQ-02 | R-STOLEN-TOKEN | `core/auth.py`, `frontend/src/api.ts`, `GET /api/auth/me` | TEST-AUTH-EXPIRY | PASS |
| AUTH-REQ-03 | R-ROLE-FORGERY | `main.py`, `docs/rbac-matrix.md`, protected APIs | TEST-AUTH-ENFORCED-RBAC | PASS |
| AUTH-REQ-04 | R-SECRET-LEAK | `main.py`, `auth_checks.py`, security events | TEST-AUTH-NO-TOKEN-LOG | PASS |
| AUTH-REQ-05 | R-AUTH-SEMANTICS | `main.py`, `api.ts`, AUTH-008 | TEST-AUTH-STATUS | PASS |
| AUTH-REQ-06 | R-CLIENT-TOKEN-LEAK | `api.ts`, `AuthPanel.tsx` | TEST-AUTH-PANEL | PASS |
| MON-REQ-01 | R-STALE-MONITORING | `MonitoringSnapshot`, `DriftBaseline`, `drift_monitoring.py` | TEST-P27-MON | PASS |
| MON-REQ-02 | R-UNCONTROLLED-DRIFT | `DriftEvaluation`, `ReleaseBlockDecision`, monitoring gate API | TEST-P27-GATE | PASS |
| REQ-MOPS-001 | R-UNAPPROVED-MODEL | `phase28_router.py`, `ModelRelease`, `ModelTransitionEvent` | `POST /api/v1/model-releases` | TEST-P28-LIFECYCLE | PASS |
| REQ-MOPS-002 | R-ARTIFACT-TAMPER | `model_artifact_validation.py`, `ModelArtifact` | `POST /api/v1/model-releases/{id}/artifact` | TEST-P28-ARTIFACT | PASS |
| REQ-MOPS-003 | R-DATA-LEAKAGE | `dataset_lineage_validation.py` | validation request | TEST-P28-LINEAGE | PASS |
| REQ-MOPS-004 | R-FABRICATED-PERFORMANCE | `model_validation_runner.py`, validation metric tables | validation run APIs | TEST-P28-NOT-MEASURED | PASS |
| REQ-MOPS-005 | R-CONFLICT-OF-DUTY | `ModelApproval`, Principal RBAC | approval API | TEST-P28-SEPARATION | PASS |
| REQ-MOPS-006 | R-UNSAFE-DEPLOYMENT | `model_deployment.py`, `ModelInferenceBinding` | deploy API | TEST-P28-GATE | PASS |
| REQ-MOPS-007 | R-ROLLBACK-FAILURE | `DeploymentRecord`, binding transaction | rollback API | TEST-P28-ROLLBACK | IMPLEMENTED; integration pending |
| REQ-MOPS-008 | R-CONSISTENCY | `modelops_checks.py` | consistency rules API | TEST-P28-RULES | PASS |
| MON-REQ-03 | R-FABRICATED-METRIC | `MonitoringDashboard.tsx`, MON-001..010 | TEST-P27-SAFETY | PASS |

## Phase 23 책임 있는 AI

| 요구사항 ID | 위험 ID | 구현 파일 | API | 테스트 ID | 결과 |
|---|---|---|---|---|---|
| RAI-REQ-01 결과 이해·신뢰도 | RAI-02, RAI-05 | `App.tsx`, `responsible_ai.py` | `GET /api/ai-literacy/confidence/{value}` | `test_transparency_content_and_cards` | PASS |
| RAI-REQ-02 단계별 latency | RAI-07 | `main.py`, `models.py` | `GET /api/ai-literacy/latency` | `test_latency_measurement_and_p95` | PASS |
| RAI-REQ-03 교육·퀴즈·접근성 | RAI-01 | `frontend/src/App.tsx` | N/A | `App.test.tsx` | PASS |
| RAI-REQ-04 사용자 동의 | RAI-02, RAI-09 | `models.py`, `main.py` | `POST /api/ai-literacy/consent` | `test_consent_version_is_recorded` | PASS |
| RAI-REQ-05 모델·데이터셋 카드 | RAI-03, RAI-04, RAI-10 | `responsible_ai.py` | `GET /api/ai-literacy/model-cards`, `dataset-cards` | `test_transparency_content_and_cards` | PASS |
| RAI-REQ-06 오분류 신고·HITL | RAI-08, RAI-09, RAI-12 | `models.py`, `main.py` | `POST /api/ai-literacy/reports` | `test_misclassification_report_forces_human_review` | PASS |
| RAI-REQ-07 대시보드·위험 등록부 | RAI-01~12 | `responsible_ai.py`, `main.py` | `GET /api/ai-literacy/dashboard`, `risks` | `test_responsible_dashboard_and_risk_registry` | PASS |

## 통합 X-ray AI 분석 지원

| 요구사항 ID | 위험 ID | 구현 파일 | API | 테스트 ID | 결과 |
|---|---|---|---|---|---|
| IXA-01 다중 라벨 소견 | RAI-02, RAI-08 | `ml/xray_findings/*` | `POST /api/v1/xray/analyze` | `test_dummy_multilabel_is_reproducible` | PASS |
| IXA-02 통합 안전 라우팅 | RAI-06, RAI-12 | `backend/app/main.py` | `POST /api/v1/xray/analyze` | `test_quality_review_get_and_clinical_review_audit` | PASS |
| IXA-03 DUMMY 히트맵 차단 | RAI-05 | `gradcam.py`, `main.py` | `GET /api/v1/xray/analyses/{id}/heatmap` | `test_integrated_png_schema_reproducibility_and_heatmap_block` | PASS |
| IXA-04 배치 제한 | RISK-ZIP-BOMB | `institution.py`, `main.py` | `POST /api/v1/xray/analyze-batch` | `test_corrupt_file_and_batch_limit` | PASS |
| IXA-05 의료진 검토·감사 | RAI-01, RAI-08 | `ClinicalReview`, `AuditEvent` | `PATCH /api/v1/xray/analyses/{id}/review` | `test_quality_review_get_and_clinical_review_audit` | PASS |

## Phase 24 종단 비교·데이터셋·모니터링

| 요구사항 ID | 위험 ID | 구현 파일 | API | 테스트 ID | 결과 |
|---|---|---|---|---|---|
| P24-01 종단 비교·조건 제한 | RAI-02, RAI-08 | `advanced_workflows.py`, `LongitudinalComparison` | `POST /api/v1/xray/longitudinal-comparisons` | `test_longitudinal_comparison_marks_acquisition_mismatch_and_review` | PASS |
| P24-02 의료진 수정·비자동 학습 | RAI-01, RAI-12 | `ActiveLearningCandidate`, `main.py` | `PATCH /api/v1/xray/analyses/{id}/review` | `test_clinical_correction_creates_anonymous_manual_candidate` | PASS |
| P24-03 데이터셋 구축·환자 분할 | RAI-03, RAI-04 | `DatasetVersion`, `advanced_workflows.py` | `POST /api/v1/datasets` | `test_dataset_patient_split_duplicate_manifest_and_approval_gate` | PASS |
| P24-04 성능 수치 생성 방지 | RAI-03, RAI-07 | `failure_metrics` | `POST /api/v1/failure-analysis` | `test_failure_analysis_does_not_invent_metrics_without_validation_data` | PASS |
| P24-05 모델 계보·문서 초안 | RAI-07, RAI-10 | `ModelDeployment`, `main.py` | `GET /api/v1/model-monitoring`, `GET /api/v1/regulatory-documents` | `test_model_monitoring_hash_and_regulatory_documents` | PASS |

## 의료기관 운영·검증

| 요구사항 ID | 위험 ID | 구현 파일 | API | 테스트 ID | 결과 |
|---|---|---|---|---|---|
| OPS-01 PACS 안전 계층 | R-PACS-UNAUTHORIZED | `services/pacs.py` | `GET /api/v1/integrations/status` | `test_priority_rule_rbac_and_pacs_not_configured` | PASS |
| OPS-02 Study 그룹·중복·방향 | R-DICOM-DUPLICATE | `Study`, `StudyInstance`, `main.py` | `POST /api/v1/studies/import` | `test_multiview_group_duplicate_block_missing_view_and_clinical_allowlist` | PASS |
| OPS-03 우선순위·사유·규칙 버전 | R-AUTOMATION-BIAS | `StudyAnalysis`, `ReviewPriorityRule` | `POST /api/v1/studies/{id}/analyze` | `test_priority_rule_rbac_and_pacs_not_configured` | PASS |
| OPS-04 Grad-CAM 제한 | R-XAI-MISUSE | `ExplanationArtifact`, `App.tsx` | `GET /api/v1/xray/analyses/{id}/gradcam-viewer` | `test_gradcam_role_and_dummy_restriction` | PASS |
| OPS-05 임상정보 allowlist | R-PHI-EXPOSURE | `services/operations.py` | `POST /api/v1/studies/import` | `test_multiview_group_duplicate_block_missing_view_and_clinical_allowlist` | PASS |
| OPS-06 Model Release Gate | R-UNAPPROVED-MODEL | `ModelRelease`, `main.py` | `/api/v1/models/*` | `test_unapproved_deploy_block_and_model_rollback` | PASS |
| OPS-07 운영 지표 | R-FABRICATED-METRIC | `ops_metrics`, `OperationsDashboard` | `GET /api/v1/monitoring/metrics` | `test_monitoring_exposes_measured_and_unknown_values` | PASS |
| OPS-08 반복 오류 CAPA | R-REPEATED-FAILURE | `OperationalCapa`, `ErrorOccurrence` | `POST/PATCH /api/v1/capa` | `test_repeated_error_creates_and_updates_capa_candidate` | PASS |
| OPS-09 역할별 권한 | R-UNAUTHORIZED-CHANGE | `require_role`, `docs/rbac-matrix.md` | 중요 변경 API | `test_priority_rule_rbac_and_pacs_not_configured` | PASS |
| REQ-26-REPRO | R-NONREPRODUCIBLE | `main.py`, `AnalysisProvenance` | `/api/v1/analyses/{id}/provenance`, `/reproduce`, `/compare/{other_id}` | `test_provenance_compare_and_explicit_reproduction_block` | PASS |
| REQ-26-TEST | R-INCOMPLETE-VALIDATION | `TestScenario`, `TestExecution` | `/api/v1/test-scenarios*` | `test_scenario_execution_and_synthetic_safety_contract` | PASS |
| REQ-26-SYNTHETIC | R-PHI | `services/verification.py` | `/api/v1/synthetic-safety-cases/{case}` | `test_scenario_execution_and_synthetic_safety_contract` | PASS |
| REQ-26-LABEL | R-LABEL-ERROR | `AnnotationRecord` | `/api/v1/annotations/*` | `test_independent_annotation_adjudication_and_approval` | PASS |
| REQ-26-FAIRNESS | R-BIAS | `fairness()` | `/api/v1/fairness/evaluate` | `test_fairness_requires_samples_and_reports_measured_values_only` | PASS |
| REQ-26-RECOVERY | R-SERVICE-FAILURE | `RecoveryJob` | `/api/v1/recovery/jobs*` | `test_recovery_idempotency_backoff_and_permissions` | PASS |
| REQ-26-AUDIT | R-AUDIT-INTEGRITY | `build_audit_package()` | `/api/v1/audit-packages*` | `test_audit_package_content_integrity_and_security_status` | PASS |
