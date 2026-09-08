import uuid
from .registry import RULES,catalog
from . import auth_checks,monitoring_checks,dicom_checks,quality_checks,model_checks,review_checks,qdrant_checks,retrieval_checks,llm_checks,api_db_checks,traceability_checks,deployment_checks,report_checks,security_checks
class ConsistencyEngine:
    version="1.0"
    def validate(self,context,categories=None):
        selected=[r for r in RULES if not categories or r.category in categories];findings=[r.check(context).dict() for r in selected]
        counts={s:sum(x["status"]==s for x in findings) for s in ("PASS","WARNING","FAIL","NOT_APPLICABLE","NOT_VERIFIABLE","BLOCKED","MANUAL_REVIEW_REQUIRED")};blocked=any(x["status"]=="FAIL" and x["severity"] in {"HIGH","CRITICAL"} for x in findings)
        return {"engine_version":self.version,"findings":findings,"summary":counts,"high_risk_block":blocked,"automatic_actions":sorted({x["automatic_action"] for x in findings if x["automatic_action"]!="NONE"}),"diagnostic_use":False}
    def catalog(self):return catalog()
