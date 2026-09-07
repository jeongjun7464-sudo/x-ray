from .base import ConsistencyRule
from .registry import register
@register
class DeploymentRule(ConsistencyRule):
    rule_id="CON-DEPLOY-001";category="MODEL_DEPLOYMENT";severity="CRITICAL"
    def check(self,c):
        model=c.get("deployment")
        if model is None:return self.finding("NOT_VERIFIABLE","모델 배포 정보를 검증할 수 없습니다.")
        required=("model_sha256","training_dataset_version","test_dataset_version","automated_tests_passed","preprocessing_version","threshold_version");missing=[x for x in required if not model.get(x)];invalid=model.get("status")=="DEPLOYED" and model.get("approval_status")!="APPROVED"
        return self.finding("FAIL" if missing or invalid else "PASS","모델·데이터셋·시험·승인·배포 연결을 확인했습니다.",list(required),{"missing":missing,"unapproved_deployment":invalid},action="BLOCK_MODEL_DEPLOYMENT" if missing or invalid else "NONE",review=bool(missing or invalid))
