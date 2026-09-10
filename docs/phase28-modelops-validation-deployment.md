# Phase 28 ModelOps 검증·배포

> 현재 상태: **PARTIAL**. 본 문서에는 목표 설계가 포함되어 있다. 서버측 검증 실행기 미연결로 검증·재시험·승인·배포는 차단된다. 경량 시그니처는 구조 검증이 아니므로 `NOT_VERIFIABLE`이다. UI 변경 버튼은 API 미연결이며 롤백·동시 배포·추론 엔진 통합은 검증 미완료다. 테스트 대역을 사용한 흐름 통과를 실제 모델 검증 통과로 해석하지 않는다. 아래 추적성 문서의 PASS는 해당 단위 시험 범위에만 해당하며 Phase 28 전체 완료를 의미하지 않는다.

Phase 28은 모델 등록과 추론 사용을 분리한다. 기본 시스템은 계속 `DEMO/DUMMY`이며 실제 승인 체크포인트가 없으면 실모델 성능을 주장하지 않는다.

## 생명주기와 책임 분리

`DRAFT → REGISTERED → ARTIFACT_VERIFIED → VALIDATION_PENDING → VALIDATING → APPROVAL_REQUIRED → APPROVED → DEPLOYMENT_PENDING → DEPLOYED` 순서를 강제한다. 실패는 `VALIDATION_FAILED`, 거절은 `REJECTED`, 운영 중단은 `SUSPENDED → ROLLED_BACK`으로 기록한다. 허용되지 않은 전이는 HTTP 409다.

- ML_ENGINEER: 메타데이터·아티팩트 등록, 검증 요청
- QA_RA: 정책과 검증 근거를 독립 검토하고 승인·거절
- ADMIN: 승인자와 다른 계정으로 Release Gate 통과 모델을 배포·롤백

## 안전 통제

- 허용 확장자, 경로, 크기, SHA-256, 경량 파일 시그니처를 검사한다.
- `.pt/.pth`는 pickle 임의 코드 실행 위험 때문에 로드하지 않고 수동 검토로 보낸다.
- 악성코드 검사와 외부 저장소는 연결되지 않았으므로 `NOT_CONFIGURED`, 원본은 `METADATA_ONLY`다.
- 이미지/익명 subject hash 중복, 미승인 라벨, PHI 필드와 manifest 무결성을 검사한다. 누수는 승인·배포를 차단한다.
- 측정값 없음은 `NOT_MEASURED`, 최소 표본 미달은 `INSUFFICIENT_DATA`이며 PASS가 아니다.

## 검증·배포·롤백

검증 정책은 ML_ENGINEER 작성, 다른 QA_RA 승인, ADMIN 활성화 순서다. 검증 요청에는 `Idempotency-Key`가 필요하다. 실제 외부 추론 서버가 없으므로 배포 계약은 `LOCAL_DEMO`; 운영 환경은 재인증 미구현으로 차단한다. Shadow는 확정 결과에 영향을 주지 않고 Canary는 최대 10%다. 롤백은 대상 승인 상태와 아티팩트 SHA-256을 다시 확인하고 활성 binding을 한 개로 교체한다.

## 정합성·CAPA

`MODEL-OPS-001`~`016`이 상태, 해시, 구조, 전처리, 누수, 정책, 지표, 역할 분리, Release Gate, 롤백, 활성 binding, 모델 카드와 미측정 PASS 오표시를 검사한다. CRITICAL 실패는 `RELEASE_BLOCK`, `INFERENCE_BLOCK`, QA_RA·ADMIN 검토 대상으로 취급한다. 반복 운영 경고는 기존 Phase 27 CAPA 후보 흐름에 연결되며 자동 승인되지 않는다.

## 운영 전 체크리스트와 한계

승인된 검증 데이터, 외부 악성코드 검사, 서명된 아티팩트 저장소, 병원 IdP 재인증, 실제 추론 서버, PACS 연동, PostgreSQL 통합시험과 규제 절차가 별도로 필요하다. 내부 승인 상태는 규제기관 승인이나 임상 사용 승인이 아니다. 이 시스템은 의료진의 진단과 치료 결정을 대체하지 않는다.
