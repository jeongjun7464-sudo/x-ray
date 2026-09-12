# 시험 시나리오 관리

## QMS 연결

TestRequirement/TestScenario/TestExecution/TestEvidence/DefectRecord를 재사용한다. 실패 실행에 결함을 연결하고 결함의 severity를 qms_data로 관리한다. CAPA 효과성 판단은 시험 ID만이 아니라 저장된 실행 상태와 증적 메타데이터를 확인한다. 실제 증적 저장소의 신뢰성과 진위 검증은 추가 작업이다.

`test_requirements`, `test_scenarios`, `test_executions`, `test_evidence`, `defect_records`가 요구사항·위험·절차·기대/실제 결과·증적 해시·재시험을 연결한다. 유형은 NORMAL, BOUNDARY, NEGATIVE, SECURITY, PERFORMANCE, RECOVERY, USABILITY이며 결과는 PASS, FAIL, BLOCKED만 허용한다. FAIL은 결함 후보를 자동 생성한다. 증적 원본 저장은 아직 `METADATA_ONLY`다.
