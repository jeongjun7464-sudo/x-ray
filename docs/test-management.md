# 시험 시나리오 관리

`test_requirements`, `test_scenarios`, `test_executions`, `test_evidence`, `defect_records`가 요구사항·위험·절차·기대/실제 결과·증적 해시·재시험을 연결한다. 유형은 NORMAL, BOUNDARY, NEGATIVE, SECURITY, PERFORMANCE, RECOVERY, USABILITY이며 결과는 PASS, FAIL, BLOCKED만 허용한다. FAIL은 결함 후보를 자동 생성한다. 증적 원본 저장은 아직 `METADATA_ONLY`다.
