from datetime import datetime,timezone
from .base import ConsistencyRule
from .registry import register

def _missing(rule,message):return rule.finding("NOT_VERIFIABLE",message)
@register
class SnapshotFreshness(ConsistencyRule):
    rule_id="MON-001";category="MODEL_MONITORING";severity="HIGH"
    def check(self,c):
        value=c.get("snapshot_created_at")
        if not value:return _missing(self,"스냅샷 시각 증적이 없습니다.")
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(value)).total_seconds()/3600;ok=age<=24;return self.finding("PASS" if ok else "FAIL","모니터링 스냅샷 최신성",24,age,action="RELEASE_BLOCK" if not ok else "NONE",review=not ok)
@register
class ModelLink(ConsistencyRule):
    rule_id="MON-002";category="MODEL_MONITORING";severity="HIGH"
    def check(self,c):
        if not c.get("model_version") or not c.get("monitoring_model_version"):return _missing(self,"모델 연결 증적이 없습니다.")
        ok=c["model_version"]==c["monitoring_model_version"];return self.finding("PASS" if ok else "FAIL","모델 버전 연결",c["model_version"],c["monitoring_model_version"],action="RELEASE_BLOCK" if not ok else "NONE",review=not ok)
@register
class DatasetBaselineLink(ConsistencyRule):
    rule_id="MON-003";category="MODEL_MONITORING";severity="HIGH"
    def check(self,c):
        if not c.get("dataset_version") or not c.get("baseline_dataset_version"):return _missing(self,"데이터셋 기준선 증적이 없습니다.")
        ok=c["dataset_version"]==c["baseline_dataset_version"];return self.finding("PASS" if ok else "FAIL","데이터셋 기준선 연결",c["dataset_version"],c["baseline_dataset_version"],action="RELEASE_BLOCK" if not ok else "NONE",review=not ok)
@register
class MinimumSample(ConsistencyRule):
    rule_id="MON-004";category="MODEL_MONITORING";severity="HIGH"
    def check(self,c):
        if "sample_size" not in c:return _missing(self,"표본 수 증적이 없습니다.")
        minimum=int(c.get("minimum_sample_size",30));ok=int(c["sample_size"])>=minimum;return self.finding("PASS" if ok else "FAIL","최소 표본 수",minimum,c["sample_size"],action="QA_RA_REVIEW" if not ok else "NONE",review=not ok)
@register
class CriticalBlock(ConsistencyRule):
    rule_id="MON-005";category="MODEL_MONITORING";severity="CRITICAL"
    def check(self,c):
        if "drift_status" not in c:return _missing(self,"드리프트·Gate 증적이 없습니다.")
        ok=c.get("drift_status")!="CRITICAL" or c.get("release_blocked") is True;return self.finding("PASS" if ok else "FAIL","CRITICAL 드리프트 배포 차단",True,c.get("release_blocked"),action="RELEASE_BLOCK" if not ok else "NONE",review=not ok)
@register
class RepeatedWarningCapa(ConsistencyRule):
    rule_id="MON-006";category="MODEL_MONITORING";severity="HIGH"
    def check(self,c):
        if "warning_count" not in c:return _missing(self,"반복 경고 증적이 없습니다.")
        required=int(c.get("warning_count",0))>=int(c.get("capa_threshold",3));ok=not required or bool(c.get("capa_candidate"));return self.finding("PASS" if ok else "FAIL","반복 경고 CAPA 연결",required,bool(c.get("capa_candidate")),action="QA_RA_REVIEW" if not ok else "NONE",review=not ok)
@register
class InsufficientDisplay(ConsistencyRule):
    rule_id="MON-007";category="MODEL_MONITORING";severity="HIGH"
    def check(self,c):
        if "sample_size" not in c:return _missing(self,"표본 표시 증적이 없습니다.")
        insufficient=int(c["sample_size"])<int(c.get("minimum_sample_size",30));ok=not insufficient or c.get("display_status")=="INSUFFICIENT_DATA";return self.finding("PASS" if ok else "FAIL","표본 부족 안전 표시","INSUFFICIENT_DATA",c.get("display_status"),action="QA_RA_REVIEW" if not ok else "NONE",review=not ok)
@register
class NoFabricatedPerformance(ConsistencyRule):
    rule_id="MON-008";category="MODEL_MONITORING";severity="CRITICAL"
    def check(self,c):
        if "validated_ground_truth" not in c:return _missing(self,"성능 산출 근거가 없습니다.")
        ok=bool(c.get("validated_ground_truth")) or c.get("clinical_performance") in {None,"NOT_MEASURED"};return self.finding("PASS" if ok else "FAIL","임상 성능 미측정값 과장 방지","NOT_MEASURED",c.get("clinical_performance"),action="RELEASE_BLOCK" if not ok else "NONE",review=not ok)
@register
class AlertResolutionEvidence(ConsistencyRule):
    rule_id="MON-009";category="MODEL_MONITORING";severity="HIGH"
    def check(self,c):
        if c.get("alert_status")!="RESOLVED":return self.finding("NOT_APPLICABLE","해결된 경고가 아닙니다.")
        ok=bool(c.get("change_reason") and c.get("resolution_evidence"));return self.finding("PASS" if ok else "FAIL","경고 해결 근거와 사유",True,ok,action="QA_RA_REVIEW" if not ok else "NONE",review=not ok)
@register
class MonitoringRbac(ConsistencyRule):
    rule_id="MON-010";category="MODEL_MONITORING";severity="CRITICAL"
    def check(self,c):
        result=c.get("monitoring_rbac_test")
        if result is None:return _missing(self,"모니터링 RBAC 시험 결과가 없습니다.")
        ok=result.get("unauthenticated")==401 and result.get("unauthorized")==403;return self.finding("PASS" if ok else "FAIL","인증·RBAC 상태 정합성",{"unauthenticated":401,"unauthorized":403},result,action="RELEASE_BLOCK" if not ok else "NONE",review=not ok)
