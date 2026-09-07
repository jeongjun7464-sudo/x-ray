from .base import ConsistencyRule
from .registry import register
@register
class DicomBodyPartRule(ConsistencyRule):
    rule_id="CON-DICOM-001";category="DICOM_AI";severity="HIGH"
    def check(self,c):
        meta=c.get("dicom_metadata",{});expected=meta.get("BodyPartExamined");actual=c.get("region")
        if not expected:return self.finding("NOT_VERIFIABLE","DICOM 촬영 부위 메타데이터가 없습니다.",actual=actual,review=True)
        ok=str(expected).upper()==str(actual).upper();return self.finding("PASS" if ok else "FAIL","DICOM 촬영 부위와 AI 예측 부위를 비교했습니다.",expected,actual,[{"source_type":"DICOM_METADATA","field":"BodyPartExamined"}],"ROUTE_TO_REVIEW" if not ok else "NONE",not ok)
@register
class DicomModalityRule(ConsistencyRule):
    rule_id="CON-DICOM-002";category="DICOM_AI";severity="CRITICAL"
    def check(self,c):
        value=c.get("dicom_metadata",{}).get("Modality")
        if value is None:return self.finding("NOT_VERIFIABLE","Modality를 검증할 수 없습니다.")
        ok=value in {"DX","CR","RG"};return self.finding("PASS" if ok else "FAIL","지원 X-ray Modality를 확인했습니다.",["DX","CR","RG"],value,action="BLOCK_AUTO_APPROVAL" if not ok else "NONE",review=not ok)
