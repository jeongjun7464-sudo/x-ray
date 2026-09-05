from __future__ import annotations
import math

CONSENT_VERSION = "ai-literacy-v1.0"
CONSENT_ITEMS = ["RESEARCH_EDUCATION_ONLY", "NOT_DIAGNOSIS", "AI_CAN_BE_WRONG", "LOW_CONFIDENCE_REVIEW", "NO_PATIENT_DATA", "NO_SOLE_MEDICAL_USE"]
REPORT_TYPES = {"REGION_ERROR", "LATERALITY_ERROR", "VIEW_ERROR", "QUALITY_ERROR", "POSSIBLE_PRIVACY_EXPOSURE", "INAPPROPRIATE_EXPLANATION", "SYSTEM_FAILURE", "OTHER"}

MODEL_CARDS = [{
    "id":"dummy-v1", "name":"Deterministic Anatomical Router", "version":"dummy-v1", "status":"DEMO / DUMMY",
    "purpose":"촬영 부위 분류 워크플로와 안전 통제 시연", "allowed_use":"합성·비식별 영상의 연구·교육용 테스트",
    "prohibited_use":"질병 진단, 치료 결정, 단독 임상 판단", "training_data":"학습하지 않은 결정론적 더미 모델",
    "validation_data":"합성 테스트 케이스", "classes":["CHEST","SPINE","HAND_WRIST","KNEE","PELVIS","SHOULDER_ARM","FOOT_ANKLE","ABDOMEN"],
    "metrics":None, "subgroups":None, "limitations":["임상 성능 미측정","실제 Grad-CAM 미제공","OOD 판정은 안전 규칙 기반"],
    "ethical_considerations":"환자정보 업로드 금지, Human-in-the-loop 필수", "approval":"DEMO_ONLY", "deployed":True,
    "last_validated":"2026-08-31", "performance_report":"/docs/validation-summary.md"
}]

DATASET_CARDS = [{
    "id":"synthetic-demo-v1", "name":"Synthetic X-ray Demo Dataset", "provider":"프로젝트 내 합성 생성기", "source":"로컬 생성",
    "terms":"연구·교육용", "image_count":None, "group_count":None, "regions":"시나리오 기반", "formats":["DICOM","PNG"],
    "labeling":"생성 시나리오 라벨", "split":"고정 테스트 케이스", "known_biases":["실제 환자·장비 분포를 대표하지 않음"],
    "restrictions":"임상 성능 평가 금지", "citation":"X-Ray Router synthetic-demo-v1"
}]

GLOSSARY = {
 "AI Literacy":"AI 결과와 한계를 이해하고 비판적으로 사용하는 능력. 예: 신뢰도를 정답 확률로 단정하지 않습니다.",
 "Confidence":"모델이 후보 중 하나를 얼마나 강하게 선택했는지 나타내는 값이며 정확도가 아닙니다.",
 "Accuracy":"정답이 있는 평가 자료에서 전체 예측 중 맞힌 비율입니다.", "Precision":"특정 클래스로 예측한 것 중 실제 해당 클래스인 비율입니다.",
 "Recall":"실제 특정 클래스 중 모델이 찾아낸 비율입니다.", "F1-score":"Precision과 Recall의 조화평균입니다.",
 "AUROC":"분류 임계값 전반의 구분 능력을 요약한 지표입니다.", "Latency":"요청부터 결과까지 걸린 시간입니다.",
 "Inference":"학습된 규칙이나 모델로 입력의 결과를 계산하는 단계입니다.", "Calibration":"신뢰도와 실제 정답 빈도가 얼마나 잘 맞는지 평가하는 과정입니다.",
 "Data Leakage":"평가에 쓰일 정보가 학습 과정에 섞여 성능이 부풀려지는 문제입니다.", "Data Drift":"운영 입력 분포가 검증 당시와 달라지는 현상입니다.",
 "Bias":"특정 집단이나 장비에서 체계적인 성능 차이가 생기는 현상입니다.", "Out-of-Distribution":"학습·지원 범위와 다른 입력입니다.",
 "Grad-CAM":"모델이 주목한 위치를 시각화하는 보조 설명이며 임상 근거를 증명하지 않습니다.", "DICOM":"의료영상과 메타데이터를 함께 담는 표준 형식입니다.",
 "PACS":"의료영상을 보관하고 전달하는 시스템입니다.", "Human-in-the-loop":"불확실한 결과를 사람이 검토하고 확정하는 방식입니다.",
 "Model Version":"재현성과 추적을 위한 모델 식별자입니다.", "Audit Log":"누가 언제 무엇을 변경했는지 남긴 기록입니다."
}

RISKS = [
 ("RAI-01","자동화 편향","검토 필요 조건과 교육","test_low_confidence_requires_review","AI Safety","MEDIUM"),
 ("RAI-02","AI 결과 과신","신뢰도 설명과 진단 면책","test_transparency_content","Product","LOW"),
 ("RAI-03","데이터 편향","하위그룹·표본 부족 표시","test_responsible_dashboard","ML","MEDIUM"),
 ("RAI-04","데이터 누수","분리 정책과 데이터셋 카드","test_cards","ML","LOW"),
 ("RAI-05","설명 가능성 오해","Grad-CAM 한계 표시","test_transparency_content","UX","LOW"),
 ("RAI-06","지원하지 않는 입력","OOD/UNKNOWN 검토 라우팅","test_low_confidence_requires_review","ML","LOW"),
 ("RAI-07","모델 드리프트","대시보드 경고","test_responsible_dashboard","MLOps","MEDIUM"),
 ("RAI-08","고신뢰도 오분류","신고 시 재검토","test_misclassification_report","Safety","MEDIUM"),
 ("RAI-09","개인정보 노출","DICOM 경고와 신고","test_misclassification_report","Privacy","MEDIUM"),
 ("RAI-10","잘못된 모델 배포","승인 상태와 모델 카드","test_cards","MLOps","LOW"),
 ("RAI-11","LLM 환각","근거 표시·쓰기 확인","test_agent_safety","AI Safety","MEDIUM"),
 ("RAI-12","잘못된 자동 라우팅","사람 검토 및 감사 로그","test_low_confidence_requires_review","Safety","MEDIUM")]

def percentile(values:list[float], q:float)->float:
    if not values:return 0.0
    ordered=sorted(values); pos=(len(ordered)-1)*q; lo=math.floor(pos); hi=math.ceil(pos)
    return ordered[lo] if lo==hi else ordered[lo]+(ordered[hi]-ordered[lo])*(pos-lo)

def confidence_explanation(value:float)->dict:
    level="HIGH" if value>=.85 else "MEDIUM" if value>=.6 else "LOW"
    messages={"HIGH":"학습·지원 분포 안에서 특정 부위를 강하게 선택한 상태입니다.","MEDIUM":"비슷한 후보가 있어 추가 확인이 필요한 상태입니다.","LOW":"영상 품질, 미지원 부위 또는 모델 한계로 사람의 검토가 필요합니다."}
    return {"level":level,"message":messages[level],"not_accuracy":"신뢰도는 정확도나 정답 확률과 같지 않습니다."}
