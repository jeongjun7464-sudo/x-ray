# 정합성 검증 규칙 카탈로그

모든 결과는 규칙 버전과 근거를 저장한다. `NOT_VERIFIABLE`은 PASS가 아니며 LLM 보조 검사는 자동 PASS가 아닌 `LLM_SUGGESTED_FINDING`으로 사람에게 전달한다.

| 규칙 ID | 규칙명 | 검증 대상·조건 | 예상 결과 | 심각도 | 실패 시 조치 | 자동화 | 요구사항 | 위험 | 시험 |
|---|---|---|---|---|---|---|---|---|---|
| CON-DICOM-001 | 부위 일치 | BodyPartExamined와 AI 부위 | 일치 | HIGH | 검토 라우팅 | 규칙 | CONS-23-A | R-METADATA | TEST-CONS-DICOM |
| CON-DICOM-002 | Modality 지원 | DX/CR/RG 여부 | 지원 Modality | CRITICAL | 자동 승인 차단 | 규칙 | CONS-23-A | R-OOD | TEST-CONS-DICOM |
| CON-QUALITY-001 | REJECT 실행 제한 | REJECT인데 COMPLETED인지 | 자동 완료 금지 | CRITICAL | 자동 승인 차단 | 규칙 | CONS-23-B | R-QUALITY | TEST-CONS-QUALITY |
| CON-MODEL-001 | 모델 식별 | 버전·SHA·dummy 표시 | 필수값 존재 | HIGH | 자동 승인 차단 | 규칙 | CONS-23-C | R-MODEL | TEST-CONS-MODEL |
| CON-REVIEW-001 | 검토 완전성 | 검토자·역할·시각 | 필수값 존재 | HIGH | 검토 라우팅 | 규칙 | CONS-23-D | R-REVIEW | TEST-CONS-REVIEW |
| CON-QDRANT-001 | Vector 정합성 | orphan·missing vector | 각각 0 | HIGH | 검색 비활성화 후보 | 규칙 | CONS-23-EF | R-KNOWLEDGE | TEST-CONS-QDRANT |
| CON-RAG-001 | Citation 정합성 | 인용이 검색 결과에 존재 | 완전 포함 | HIGH | 검토 라우팅 | 규칙 | CONS-23-G | R-HALLUCINATION | TEST-CONS-RAG |
| CON-LLM-001 | 의미 일치 후보 | sLLM 답변과 근거 | 사람 확인 | MEDIUM | 수동 검토 | LLM 제안 | CONS-29 | R-HALLUCINATION | TEST-CONS-LLM |
| CON-API-001 | 화면 상태 | REVIEW_REQUIRED를 완료 표시하지 않음 | 상태 일치 | HIGH | 검토 라우팅 | 규칙 | CONS-23-I | R-UI | TEST-CONS-API |
| CON-TRACE-001 | 추적성 | 요구사항·위험·시험·결과 | 모든 연결 존재 | HIGH | 자동 승인 차단 | 규칙 | CONS-23-J | R-TRACE | TEST-CONS-TRACE |
| CON-DEPLOY-001 | 배포 Gate | SHA·데이터·시험·전처리·임계값·승인 | 필수값과 승인 | CRITICAL | 모델 배포 차단 | 규칙 | CONS-23-K | R-DEPLOY | TEST-CONS-DEPLOY |
| CON-REPORT-001 | 보고서 원본 | analysis ID와 연구용 표시 | 원본과 일치 | HIGH | 재생성 필요 | 규칙 | CONS-23-L | R-REPORT | TEST-CONS-REPORT |
| CON-SECURITY-001 | Prompt 개인정보 | Prompt PHI 패턴 | 개인정보 없음 | CRITICAL | 자동 승인 차단 | 규칙 | CONS-23-H | R-PHI | TEST-CONS-SECURITY |

허용 자동 조치는 검토 라우팅, 승인·배포 차단, 보고서 재생성 표시, 문서 검색 비활성화, 알림과 재검증 예약뿐이다. 의료진 결과·원본 DICOM·문서 내용 수정, 모델 승인·배포와 CAPA 종료는 자동화하지 않는다.
