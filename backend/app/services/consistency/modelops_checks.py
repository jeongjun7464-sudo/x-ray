from .base import ConsistencyRule
from .registry import register

CHECKS=[
("MODEL-OPS-001","state_transition_valid","유효한 모델 상태 전이","HIGH"),("MODEL-OPS-002","checkpoint_hash_match","체크포인트 SHA-256 일치","CRITICAL"),("MODEL-OPS-003","output_labels_match","모델 출력과 라벨 사전 일치","HIGH"),("MODEL-OPS-004","preprocessing_version_match","전처리 버전 일치","HIGH"),("MODEL-OPS-005","no_data_leakage","학습·시험 데이터 누수 없음","CRITICAL"),("MODEL-OPS-006","validation_policy_linked","검증 정책 버전 연결","HIGH"),("MODEL-OPS-007","required_metrics_measured","필수 지표 측정","HIGH"),("MODEL-OPS-008","minimum_sample_met","최소 표본 수 충족","HIGH"),("MODEL-OPS-009","registerer_approver_separated","등록자와 승인자 분리","CRITICAL"),("MODEL-OPS-010","approver_deployer_separated","승인자와 배포자 분리","CRITICAL"),("MODEL-OPS-011","release_gate_passed","배포 전 Release Gate 통과","CRITICAL"),("MODEL-OPS-012","rollback_target_valid","롤백 대상 유효성","HIGH"),("MODEL-OPS-013","single_active_model","활성 모델 단일성","CRITICAL"),("MODEL-OPS-014","binding_matches_deployment","배포 모델과 추론 모델 일치","CRITICAL"),("MODEL-OPS-015","model_card_matches","모델 카드와 실제 설정 일치","HIGH"),("MODEL-OPS-016","no_false_pass_for_unmeasured","미측정 지표 PASS 오표시 방지","CRITICAL")]
def make_rule(rule_id,key,label,severity):
    def check(self,c):
        if key not in c:return self.finding("NOT_VERIFIABLE",f"{label} 증적이 없습니다.")
        ok=bool(c[key]);return self.finding("PASS" if ok else "FAIL",label,True,c[key],action="RELEASE_BLOCK" if not ok else "NONE",review=not ok)
    return type(rule_id.replace("-","_"),(ConsistencyRule,),{"rule_id":rule_id,"category":"MODEL_OPS","severity":severity,"check":check})
for args in CHECKS:register(make_rule(*args))
