# Phase 30 QMS — PARTIAL / 연구용 검토 단계

문서번호: QMS-P30-001 · 버전: 0.2 · 상태: DRAFT · 작성자 역할: 개발 지원 · 검토자 역할: QA_RA · 승인 상태: 미승인 · 발효일: 없음.

내용 SHA-256: phase30-document-manifest.json 참조. 관련 요구사항: REQ-QMS-01~06. 관련 위험: R-QMS-INTEGRITY. 관련 시험: backend/tests/test_phase30_workflows.py 및 test_phase30_draft.py, frontend/src/QmsCenter.test.tsx.

## 현재 저장한 개발 초안

- 기존 TestRequirement, AIRisk, OperationalCapa, DefectRecord에 qms_data를 추가하여 중복 레코드 체계를 피한다.
- ControlledDocument/Version, DocumentReview, ElectronicApproval, TraceabilityLink, ChangeRequest, ImpactAssessment, AuditEvidence, AuditChainEntry 스키마 및 0016_qms 마이그레이션.
- `/api/v1/qms` router를 FastAPI에 등록했다. 요구사항 작성·모호성 경고·검토 요청, 위험 계산, 양방향 추적성·대상 존재/버전/코드 해시 검사, 변경 영향평가, CAPA, 문서 버전과 독립 검토, 감사 패키지 API를 제공한다. 상세 경로는 실행 중 `/openapi.json`에서 확인한다.
- 생성과 검증 모듈을 분리했다. 기본은 결정적 템플릿이며 sLLM은 QMS_SLLM_ENABLED와 use_sllm의 명시적 선택이 필요하다. 기존 HybridRetriever와 LLM client를 사용하는 읽기 전용 LangGraph는 근거가 없으면 NO_EVIDENCE, dummy이면 DUMMY로 반환한다. 실제 Qdrant·sLLM 서버 연결은 NOT_VERIFIED다. 인용 ID 존재 확인은 주장과 근거의 의미적 일치를 증명하지 않는다.
- 전자승인 게이트는 재인증 미설정으로 차단한다. 승인 성공 또는 법적 전자서명 기능은 제공하지 않는다.
- 감사 체인 서비스 초안: 외부 신뢰 앵커·기존 로그 백필·운영 동시성 재시도는 미구현. 운영 감사 체인으로 사용하면 안 된다.
- React QMS 관리센터를 연결했다. 목록·필터·구조화 JSON 입력·작업 요청·위험 표·추적성 그래프/CSV·패키지 다운로드를 사용한다. 폼은 기술 사용자용이며 일반 사용자 친화적인 전용 입력 폼은 추가 개선 대상이다.
- QMS-001~020 규칙을 등록했다. 실제 DB에 없는 근거는 NOT_VERIFIABLE이다. 규칙 통과는 해당 코드 검사에 한정되며 표준 적합성이나 임상 성능 검증이 아니다.
- 관련 미완료 변경/HIGH·CRITICAL CAPA, 미해결 CRITICAL 위험 및 무결성 실패를 배포 차단 게이트에 연결했다. QMS로 생성한 CAPA·패키지는 기존 비보호 API로 변경하거나 내려받을 수 없다.
- 패키지는 원본 영상·자유 텍스트를 제외한 구조화 메타데이터만 포함하는 INCOMPLETE_DRAFT ZIP이다. 파일별 해시·ZIP 해시·manifest 일치를 검증한다. 완전한 규제 제출 자료를 생성한 것으로 표현하지 않는다.

## 남은 작업

재인증 제공자와 승인 이후 전체 운영 수명주기, 전체 레거시 승인 경로의 전자승인 전환, 실제 시험 증적 저장소의 신뢰 검증, 규제 제출용 전체 본문 패키지, 운영 동시성·부하 시험, 실제 브라우저 모바일·접근성 검증은 남아 있다. PostgreSQL, 실제 PACS/FHIR, 실제 Qdrant/sLLM 및 규제 적합성은 NOT_VERIFIED다. 개인정보 검사는 휴리스틱이며 실제 환자 자료를 안전하게 수용한다는 의미가 아니다. 기존 QMS 미연결 감사 이벤트는 자동 인증하지 않는다.

## 시험 기록

2026-09-12 기준 백엔드·ML 전체 116 passed, FastAPI on_event 사용 중단 예정 경고 2개. 프론트엔드 13 files / 32 tests passed. TypeScript 및 Vite 빌드 통과(1811 modules). pnpm install --frozen-lockfile --offline은 Already up to date. SQLite Alembic upgrade → downgrade 0015_integrations → upgrade 0016_qms 통과. 최신 상태 전이 API와 승인 우회 차단 시험을 포함한 결과다.

첫 회귀 실행에서는 Windows 임시 디렉터리 권한 때문에 ML 테스트 1개가 setup ERROR였다. 새 workspace basetemp에서 재실행했다. 프론트엔드는 초기 테스트 cleanup 누락 2건과 ByRoleOptions 타입 오류 1건을 수정했다. 기존 테스트를 삭제하거나 skip하지 않았다. Docker CLI가 없어 Docker/실제 PostgreSQL 검증은 실행하지 못했다.

## 실행 방법

backend 작업 폴더에서 `python -m alembic upgrade head` 후 `python -m uvicorn app.main:app`을 실행한다. frontend에서 `pnpm dev`로 열고 서명 세션으로 로그인한 다음 QMS·규제 대응 관리센터를 선택한다. QA_RA가 작성·검토, ML_ENGINEER가 허용된 기술 요구사항·초안 작성, 기타 허용 역할이 조회를 수행한다. ADMIN은 QMS 승인자를 대신하지 않는다.

재현 시험은 저장소 루트에서 PYTHONPATH를 backend와 ml로 설정하고 새 임시 디렉터리를 --basetemp로 지정해 `python -m pytest backend/tests ml/tests -q`를 실행한다. 테스트는 합성 데이터와 모의 클라이언트를 사용하며 실측 임상 성능을 만들지 않는다.

## 표준·규정 검토 범위

IEC 62304, ISO 14971, IEC 62366-1, IEC 81001-5-1, ISO 13485, ISO/IEC 27001, DICOM, HL7 FHIR, 국내 의료기기 소프트웨어 요구사항, EU MDR, FDA 소프트웨어 문서화는 QA/RA 적용성 검토 대상 목록이다. 특정 판본·조항을 모두 구현했거나 적합성을 확인했다는 의미가 아니다. 원문을 저장소에 복제하지 않는다.

[ISO 14971 공식 개요](https://www.iso.org/standard/72704.html)는 위험관리 프로세스의 참고 자료다. [FDA 소프트웨어 제출 문서 지침](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/content-premarket-submissions-device-software-functions)은 문서 구성 검토용 참고 자료이며 이 프로젝트의 승인 근거가 아니다.

기존 DB를 사용할 경우 backend에서 Alembic upgrade head가 필요하다. create_all은 기존 테이블에 컬럼을 추가하지 않는다. 이 WIP는 main에 병합하거나 운영 배포할 단계가 아니다.

생성 문서는 QA/RA와 권한 있는 담당자의 검토·승인이 필요한 초안이다. 의료기기 인증, 특정 표준 적합성 또는 법적 전자서명 요건 충족을 주장하지 않는다. 실제 환자정보와 의료영상 입력은 금지한다.
